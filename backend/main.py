from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pandas as pd
import io
from typing import Optional, List
import os
from datetime import datetime

app = FastAPI(title="Excel Data Manager API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to store current data
current_data = None
current_filename = None

def load_initial_data():
    """Load initial data if available"""
    global current_data, current_filename
    # Look for existing Excel files in the current directory
    excel_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls', '.csv'))]
    if excel_files:
        try:
            file_path = excel_files[0]  # Use the first Excel file found
            if file_path.endswith('.csv'):
                current_data = pd.read_csv(file_path)
            else:
                current_data = pd.read_excel(file_path)
            current_filename = file_path
            print(f"Loaded initial data from {file_path}")
        except Exception as e:
            print(f"Error loading initial data: {e}")

@app.on_event("startup")
async def startup_event():
    load_initial_data()

@app.get("/")
async def root():
    return {"message": "Excel Data Manager API", "status": "running"}

@app.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    """Upload and replace current Excel data"""
    global current_data, current_filename
    
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="File must be Excel (.xlsx, .xls) or CSV (.csv)")
    
    try:
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            # Handle CSV files
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            # Handle Excel files
            df = pd.read_excel(io.BytesIO(contents))
        
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        # Save the file locally (optional - for persistence)
        file_path = f"uploaded_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        if file.filename.endswith('.csv'):
            df.to_csv(file_path, index=False)
        else:
            df.to_excel(file_path, index=False)
        
        current_data = df
        current_filename = file.filename
        
        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/data")
async def get_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    subscriber_name: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    is_open: Optional[str] = Query(None),
    branch_name: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    needs_password_change: Optional[str] = Query(None)
):
    """Get filtered and paginated data"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available. Please upload an Excel file first.")
    
    df = current_data.copy()
    
    # Apply filters
    if subscriber_name:
        df = df[df['Subscriber Name'].str.contains(subscriber_name, case=False, na=False)]
    
    if name:
        df = df[df['Name'].str.contains(name, case=False, na=False)]
    
    if username:
        df = df[df['Username'].str.contains(username, case=False, na=False)]
    
    if email:
        df = df[df['Email'].str.contains(email, case=False, na=False)]
    
    if is_open:
        df = df[df['Is Open'].str.contains(is_open, case=False, na=False)]
    
    if branch_name:
        df = df[df['Branch Name'].str.contains(branch_name, case=False, na=False)]
    
    if position:
        df = df[df['Position'].str.contains(position, case=False, na=False)]
    
    if needs_password_change:
        df = df[df['Needs To Change Password'].str.contains(needs_password_change, case=False, na=False)]
    
    # Calculate pagination
    total_records = len(df)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    # Get paginated data
    paginated_df = df.iloc[start_idx:end_idx]
    
    # Convert to dict and handle NaN values
    data = paginated_df.fillna('').to_dict('records')
    
    return {
        "data": data,
        "total_records": total_records,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_records + page_size - 1) // page_size,
        "has_next": end_idx < total_records,
        "has_previous": page > 1
    }

@app.get("/download-excel")
async def download_filtered_excel(
    subscriber_name: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    is_open: Optional[str] = Query(None),
    branch_name: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    needs_password_change: Optional[str] = Query(None)
):
    """Download filtered data as Excel file"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data.copy()
    
    # Apply same filters as get_data
    if subscriber_name:
        df = df[df['Subscriber Name'].str.contains(subscriber_name, case=False, na=False)]
    if name:
        df = df[df['Name'].str.contains(name, case=False, na=False)]
    if username:
        df = df[df['Username'].str.contains(username, case=False, na=False)]
    if email:
        df = df[df['Email'].str.contains(email, case=False, na=False)]
    if is_open:
        df = df[df['Is Open'].str.contains(is_open, case=False, na=False)]
    if branch_name:
        df = df[df['Branch Name'].str.contains(branch_name, case=False, na=False)]
    if position:
        df = df[df['Position'].str.contains(position, case=False, na=False)]
    if needs_password_change:
        df = df[df['Needs To Change Password'].str.contains(needs_password_change, case=False, na=False)]
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Filtered_Data', index=False)
    
    output.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"filtered_data_{timestamp}.xlsx"
    
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/filter-options")
async def get_filter_options():
    """Get unique values for filter dropdowns"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data
    
    return {
        "subscriber_names": sorted([x for x in df['Subscriber Name'].dropna().unique() if x]),
        "branch_names": sorted([x for x in df['Branch Name'].dropna().unique() if x]),
        "positions": sorted([x for x in df['Position'].dropna().unique() if x]),
        "is_open_options": sorted([x for x in df['Is Open'].dropna().unique() if x]),
        "password_change_options": sorted([x for x in df['Needs To Change Password'].dropna().unique() if x])
    }

@app.get("/stats")
async def get_stats():
    """Get basic statistics about the data"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data
    
    return {
        "total_records": len(df),
        "active_users": len(df[df['Is Open'] == 'Yes']),
        "inactive_users": len(df[df['Is Open'] == 'No']),
        "unique_subscribers": df['Subscriber Name'].nunique(),
        "unique_branches": df['Branch Name'].nunique(),
        "users_need_password_change": len(df[df['Needs To Change Password'] == 'Yes']),
        "filename": current_filename
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)