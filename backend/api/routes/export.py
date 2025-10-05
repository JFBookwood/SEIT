from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import json
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from ..database import get_db
from ..models import SensorData, AnalysisJob

router = APIRouter()

@router.get("/sensor-data/csv")
async def export_sensor_data_csv(
    bbox: str,  # "west,south,east,north"
    start_date: str,
    end_date: str,
    parameters: List[str] = None,
    db: Session = Depends(get_db)
):
    """Export sensor data as CSV"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        query = db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start,
            SensorData.timestamp <= end
        )
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No data found for export")
        
        # Convert to DataFrame
        data = []
        for result in results:
            row = {
                'sensor_id': result.sensor_id,
                'latitude': result.latitude,
                'longitude': result.longitude,
                'timestamp': result.timestamp.isoformat(),
                'source': result.source
            }
            
            # Add parameter columns
            if not parameters or 'pm25' in parameters:
                row['pm25'] = result.pm25
            if not parameters or 'pm10' in parameters:
                row['pm10'] = result.pm10
            if not parameters or 'temperature' in parameters:
                row['temperature'] = result.temperature
            if not parameters or 'humidity' in parameters:
                row['humidity'] = result.humidity
            if not parameters or 'pressure' in parameters:
                row['pressure'] = result.pressure
                
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Create CSV in memory
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        # Create filename
        filename = f"seit_sensor_data_{start_date}_{end_date}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting CSV: {str(e)}")

@router.get("/sensor-data/geojson")
async def export_sensor_data_geojson(
    bbox: str,
    start_date: str,
    end_date: str,
    aggregate: bool = True,
    db: Session = Depends(get_db)
):
    """Export sensor data as GeoJSON"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        query = db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start,
            SensorData.timestamp <= end
        )
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No data found for export")
        
        features = []
        
        if aggregate:
            # Aggregate by sensor location
            sensor_groups = {}
            for result in results:
                key = (result.sensor_id, result.latitude, result.longitude)
                if key not in sensor_groups:
                    sensor_groups[key] = []
                sensor_groups[key].append(result)
            
            for (sensor_id, lat, lon), sensor_data in sensor_groups.items():
                # Calculate aggregates
                pm25_values = [r.pm25 for r in sensor_data if r.pm25 is not None]
                pm10_values = [r.pm10 for r in sensor_data if r.pm10 is not None]
                
                properties = {
                    "sensor_id": sensor_id,
                    "source": sensor_data[0].source,
                    "record_count": len(sensor_data),
                    "time_range": {
                        "start": min(r.timestamp for r in sensor_data).isoformat(),
                        "end": max(r.timestamp for r in sensor_data).isoformat()
                    }
                }
                
                if pm25_values:
                    properties["pm25"] = {
                        "mean": sum(pm25_values) / len(pm25_values),
                        "min": min(pm25_values),
                        "max": max(pm25_values)
                    }
                
                if pm10_values:
                    properties["pm10"] = {
                        "mean": sum(pm10_values) / len(pm10_values),
                        "min": min(pm10_values),
                        "max": max(pm10_values)
                    }
                
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "properties": properties
                }
                features.append(feature)
        else:
            # Individual records
            for result in results:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [result.longitude, result.latitude]
                    },
                    "properties": {
                        "sensor_id": result.sensor_id,
                        "timestamp": result.timestamp.isoformat(),
                        "pm25": result.pm25,
                        "pm10": result.pm10,
                        "temperature": result.temperature,
                        "humidity": result.humidity,
                        "pressure": result.pressure,
                        "source": result.source
                    }
                }
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "export_info": {
                    "bbox": [west, south, east, north],
                    "time_range": {"start": start_date, "end": end_date},
                    "total_features": len(features),
                    "aggregated": aggregate,
                    "generated_at": datetime.utcnow().isoformat()
                }
            }
        }
        
        filename = f"seit_sensor_data_{start_date}_{end_date}.geojson"
        
        return StreamingResponse(
            io.BytesIO(json.dumps(geojson, indent=2).encode('utf-8')),
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting GeoJSON: {str(e)}")

@router.get("/report/pdf")
async def generate_pdf_report(
    bbox: str,
    start_date: str,
    end_date: str,
    include_hotspots: bool = True,
    include_trends: bool = True,
    db: Session = Depends(get_db)
):
    """Generate comprehensive PDF report"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        
        # Create temporary file
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        # Create PDF document
        doc = SimpleDocTemplate(temp_file.name, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.darkblue,
            spaceAfter=30
        )
        story.append(Paragraph("SEIT Environmental Impact Report", title_style))
        story.append(Spacer(1, 12))
        
        # Report metadata
        story.append(Paragraph(f"<b>Report Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", styles['Normal']))
        story.append(Paragraph(f"<b>Time Period:</b> {start_date} to {end_date}", styles['Normal']))
        story.append(Paragraph(f"<b>Geographic Bounds:</b> [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}]", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Get summary statistics
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        query = db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start_dt,
            SensorData.timestamp <= end_dt
        )
        
        results = query.all()
        
        if not results:
            story.append(Paragraph("No data available for the specified region and time period.", styles['Normal']))
        else:
            # Summary section
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            
            pm25_values = [r.pm25 for r in results if r.pm25 is not None]
            unique_sensors = len(set(r.sensor_id for r in results))
            
            summary_data = [
                ["Metric", "Value"],
                ["Total Sensor Records", str(len(results))],
                ["Unique Sensors", str(unique_sensors)],
                ["Data Sources", ", ".join(set(r.source for r in results))],
            ]
            
            if pm25_values:
                import numpy as np
                summary_data.extend([
                    ["Average PM2.5 (μg/m³)", f"{np.mean(pm25_values):.2f}"],
                    ["Max PM2.5 (μg/m³)", f"{np.max(pm25_values):.2f}"],
                    ["Min PM2.5 (μg/m³)", f"{np.min(pm25_values):.2f}"],
                ])
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Data quality assessment
            story.append(Paragraph("Data Quality Assessment", styles['Heading2']))
            
            quality_metrics = []
            if pm25_values:
                completeness = len(pm25_values) / len(results) * 100
                quality_metrics.append(f"PM2.5 Data Completeness: {completeness:.1f}%")
            
            temp_values = [r.temperature for r in results if r.temperature is not None]
            if temp_values:
                completeness = len(temp_values) / len(results) * 100
                quality_metrics.append(f"Temperature Data Completeness: {completeness:.1f}%")
            
            for metric in quality_metrics:
                story.append(Paragraph(f"• {metric}", styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # Recommendations
            story.append(Paragraph("Recommendations", styles['Heading2']))
            
            recommendations = []
            if pm25_values:
                avg_pm25 = np.mean(pm25_values)
                if avg_pm25 > 35:  # WHO guideline
                    recommendations.append("PM2.5 levels exceed WHO guidelines. Consider air quality improvement measures.")
                elif avg_pm25 > 15:
                    recommendations.append("PM2.5 levels are elevated. Monitor trends and consider preventive actions.")
                else:
                    recommendations.append("PM2.5 levels are within acceptable ranges.")
            
            recommendations.extend([
                "Continue monitoring sensor network coverage in this region.",
                "Ensure regular calibration and maintenance of sensors.",
                "Consider expanding sensor network in areas with data gaps."
            ])
            
            for rec in recommendations:
                story.append(Paragraph(f"• {rec}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        filename = f"seit_report_{start_date}_{end_date}.pdf"
        
        return FileResponse(
            temp_file.name,
            media_type="application/pdf",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF report: {str(e)}")

@router.get("/analysis/{job_id}/results")
async def export_analysis_results(
    job_id: str,
    format: str = "json",  # json, csv, geojson
    db: Session = Depends(get_db)
):
    """Export analysis results in various formats"""
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        
        if job.status != "completed":
            raise HTTPException(status_code=400, detail="Analysis job not completed")
        
        # In a real implementation, you'd load results from file system
        # For demo, return mock results structure
        mock_results = {
            "job_id": job_id,
            "job_type": job.job_type,
            "parameters": job.parameters,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "results": {
                "message": "Results would be loaded from storage",
                "format": format,
                "available_formats": ["json", "csv", "geojson"]
            }
        }
        
        filename = f"seit_analysis_{job_id}.{format}"
        
        if format == "json":
            return StreamingResponse(
                io.BytesIO(json.dumps(mock_results, indent=2).encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        elif format == "csv":
            # Convert to CSV format
            df = pd.DataFrame([mock_results])
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting analysis results: {str(e)}")
