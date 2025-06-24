from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd
import io
from typing import Optional, List, Dict
import os
from datetime import datetime
import traceback

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

# Columns to exclude from Excel downloads
EXCLUDED_COLUMNS = ['Is Open', 'Position', 'Expiry Date', 'Needs To Change Password']

def create_excel_buffer(df, sheet_name='Data'):
    """Helper function to create a properly formatted Excel file in memory"""
    try:
        # Clean the dataframe
        df_clean = df.copy()
        
        # Handle any potential data issues
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                # Convert to string and replace nan values
                df_clean[col] = df_clean[col].astype(str).replace(['nan', 'None', 'NaN'], '')
            # Fill any remaining NaN values
            df_clean[col] = df_clean[col].fillna('')
        
        # Create Excel file in memory
        excel_buffer = io.BytesIO()
        
        # Use openpyxl engine with proper options
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_clean.to_excel(writer, sheet_name=sheet_name, index=False, na_rep='')
        
        # Get content and verify it's not empty
        excel_content = excel_buffer.getvalue()
        
        if len(excel_content) == 0:
            raise ValueError("Generated Excel file is empty")
        
        return excel_content
        
    except Exception as e:
        print(f"Error in create_excel_buffer: {e}")
        raise Exception(f"Error creating Excel file: {str(e)}")

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

def filter_dataframe_for_download_all(df):
    """Apply filters for 'Download All' functionality"""
    # Check if 'Is Open' column exists
    if 'Is Open' not in df.columns:
        print("Warning: 'Is Open' column not found, returning all data")
        return df.copy()
    
    # Filter for active users only (Is Open = 'Yes')
    # Handle different possible values (case-insensitive)
    filtered_df = df[df['Is Open'].astype(str).str.lower().isin(['yes', 'true', '1', 'active'])].copy()
    
    print(f"Original records: {len(df)}, Filtered records: {len(filtered_df)}")
    print(f"Unique 'Is Open' values in original data: {df['Is Open'].unique()}")
    
    return filtered_df

def prepare_dataframe_for_excel(df):
    """Remove excluded columns from dataframe for Excel download"""
    df_copy = df.copy()
    
    # Remove excluded columns if they exist
    columns_to_remove = [col for col in EXCLUDED_COLUMNS if col in df_copy.columns]
    if columns_to_remove:
        df_copy = df_copy.drop(columns=columns_to_remove)
        print(f"Removed columns for Excel: {columns_to_remove}")
    
    return df_copy


def create_safe_filename(name, fallback_prefix="File"):
    """Create a safe filename from a string"""
    if not name or str(name).strip() == '':
        return f"{fallback_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Keep only alphanumeric characters, spaces, hyphens, and underscores
    safe_name = "".join(c for c in str(name) if c.isalnum() or c in (' ', '-', '_')).strip()
    
    # If the safe name is empty after cleaning, use fallback
    if not safe_name:
        safe_name = f"{fallback_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Limit length to 50 characters
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    
    return safe_name

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
    
    # Remove excluded columns for Excel download
    df = prepare_dataframe_for_excel(df)
    
    try:
        # Create Excel file using helper function
        excel_content = create_excel_buffer(df, 'Filtered_Data')
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"filtered_data_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        print(f"Error in download_filtered_excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating Excel file: {str(e)}")

@app.get("/download-all")
async def download_all_data():
    """Download all data without any filters"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data.copy()
    
    # Remove excluded columns for Excel download
    df = prepare_dataframe_for_excel(df)
    
    try:
        # Create Excel file using helper function
        excel_content = create_excel_buffer(df, 'All_Data')
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"all_data_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        print(f"Error in download_all_data: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating Excel file: {str(e)}")

@app.get("/download-by-subscriber")
async def download_by_subscriber(subscriber: str = Query(..., description="Subscriber name to filter by")):
    """Download data for a specific subscriber"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data.copy()
    
    # Filter by exact subscriber name match
    filtered_df = df[df['Subscriber Name'] == subscriber]
    
    if len(filtered_df) == 0:
        raise HTTPException(status_code=404, detail=f"No data found for subscriber: {subscriber}")
    
    # Remove excluded columns for Excel download
    filtered_df = prepare_dataframe_for_excel(filtered_df)
    
    try:
        # Create Excel file using helper function
        excel_content = create_excel_buffer(filtered_df, 'Subscriber_Data')
        
        # Generate filename with timestamp and subscriber name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_subscriber_name = create_safe_filename(subscriber, "Subscriber")
        filename = f"subscriber_{safe_subscriber_name}_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        print(f"Error in download_by_subscriber: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating Excel file: {str(e)}")

# NEW ENDPOINTS FOR SEQUENTIAL DOWNLOADS

@app.get("/get-subscribers-list")
async def get_subscribers_list():
    """Get list of all subscribers for sequential download
    Filters: Is Open = 'Yes' only"""
    
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available. Please upload an Excel file first.")
    
    try:
        df = current_data.copy()
        print(f"Original data shape: {df.shape}")
        
        # Apply filtering for active users only
        if 'Is Open' not in df.columns:
            print("WARNING: 'Is Open' column not found, using all data")
            filtered_df = df.copy()
        else:
            filtered_df = filter_dataframe_for_download_all(df)
        
        print(f"After filtering, shape: {filtered_df.shape}")
        
        if len(filtered_df) == 0:
            available_values = df['Is Open'].unique() if 'Is Open' in df.columns else ['Column not found']
            raise HTTPException(
                status_code=404, 
                detail=f"No active users found. Available 'Is Open' values: {list(available_values)}"
            )
        
        # Check for Subscriber Name column
        if 'Subscriber Name' not in filtered_df.columns:
            raise HTTPException(status_code=404, detail="'Subscriber Name' column not found in data")
        
        # Get unique subscribers with their record counts
        subscriber_stats = filtered_df.groupby('Subscriber Name').size().reset_index(name='record_count')
        subscriber_stats = subscriber_stats.sort_values('Subscriber Name')
        
        subscribers_list = []
        for _, row in subscriber_stats.iterrows():
            subscribers_list.append({
                "name": row['Subscriber Name'],
                "record_count": int(row['record_count']),
                "safe_filename": create_safe_filename(row['Subscriber Name'], "Subscriber")
            })
        
        print(f"Found {len(subscribers_list)} subscribers")
        
        return {
            "total_subscribers": len(subscribers_list),
            "total_records": len(filtered_df),
            "subscribers": subscribers_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_subscribers_list: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting subscribers list: {str(e)}")

@app.get("/download-subscriber-by-name")
async def download_subscriber_by_name(subscriber_name: str = Query(..., description="Exact subscriber name")):
    """Download data for a specific subscriber by exact name match
    This endpoint is used for sequential downloads"""
    
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    try:
        df = current_data.copy()
        
        # Apply filtering for active users only
        filtered_df = filter_dataframe_for_download_all(df)
        
        if len(filtered_df) == 0:
            raise HTTPException(status_code=404, detail="No active users found")
        
        # Filter by exact subscriber name match
        subscriber_df = filtered_df[filtered_df['Subscriber Name'] == subscriber_name].copy()
        
        if len(subscriber_df) == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"No active records found for subscriber: {subscriber_name}"
            )
        
        # Remove excluded columns for Excel download
        prepared_df = prepare_dataframe_for_excel(subscriber_df)
        
        # Create Excel file using helper function
        excel_content = create_excel_buffer(prepared_df, 'Data')
        
        # Generate filename with subscriber name
        safe_subscriber_name = create_safe_filename(subscriber_name, "Subscriber")
        filename = f"{safe_subscriber_name}_data.xlsx"
        
        print(f"Created Excel file for subscriber '{subscriber_name}': {filename} ({len(excel_content)} bytes)")
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in download_subscriber_by_name: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error creating Excel file: {str(e)}")

# KEEP ORIGINAL ENDPOINT FOR BACKWARD COMPATIBILITY (but renamed for clarity)
@app.get("/download-all-by-subscribers-zip")
async def download_all_by_subscribers_zip():
    """Download separate Excel files for each subscriber, all in one ZIP file
    Filters: Is Open = 'Yes' only, excludes specified columns from Excel files"""
    
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available. Please upload an Excel file first.")
    
    try:
        df = current_data.copy()
        print(f"Original data shape: {df.shape}")
        
        # Apply filtering for active users only (Is Open = 'Yes')
        if 'Is Open' in df.columns:
            # Filter for active users - handle different possible values
            filtered_df = df[df['Is Open'].astype(str).str.lower().isin(['yes', 'true', '1', 'active'])].copy()
            print(f"After filtering for active users: {filtered_df.shape}")
        else:
            print("WARNING: 'Is Open' column not found, using all data")
            filtered_df = df.copy()
        
        if len(filtered_df) == 0:
            raise HTTPException(status_code=404, detail="No active users found for download")
        
        # Check for Subscriber Name column
        if 'Subscriber Name' not in filtered_df.columns:
            raise HTTPException(status_code=404, detail="'Subscriber Name' column not found in data")
        
        # Get unique subscribers
        unique_subscribers = filtered_df['Subscriber Name'].dropna().unique()
        print(f"Found {len(unique_subscribers)} unique subscribers")
        
        if len(unique_subscribers) == 0:
            raise HTTPException(status_code=404, detail="No subscribers found in filtered data")
        
        # Create ZIP file
        import zipfile
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
            files_created = 0
            summary_data = {
                'Subscriber_Name': [],
                'Records_Count': [],
                'Excel_Filename': []
            }
            
            for subscriber in unique_subscribers:
                try:
                    # Filter data for this subscriber
                    subscriber_df = filtered_df[filtered_df['Subscriber Name'] == subscriber].copy()
                    
                    if len(subscriber_df) == 0:
                        continue
                    
                    # Remove excluded columns for Excel download
                    prepared_df = prepare_dataframe_for_excel(subscriber_df)
                    
                    # Create Excel file for this subscriber
                    excel_content = create_excel_buffer(prepared_df, 'Data')
                    
                    # Create safe filename using subscriber name
                    safe_subscriber_name = create_safe_filename(subscriber, f"Subscriber_{files_created + 1}")
                    filename = f"{safe_subscriber_name}.xlsx"
                    
                    # Add to ZIP
                    zip_file.writestr(filename, excel_content)
                    files_created += 1
                    
                    # Add to summary
                    summary_data['Subscriber_Name'].append(subscriber)
                    summary_data['Records_Count'].append(len(subscriber_df))
                    summary_data['Excel_Filename'].append(filename)
                    
                    print(f"Created file: {filename} with {len(subscriber_df)} records")
                    
                except Exception as e:
                    print(f"Error processing subscriber '{subscriber}': {e}")
                    continue
            
            if files_created == 0:
                raise HTTPException(status_code=500, detail="No Excel files could be created")
            
            # Add summary file
            if summary_data['Subscriber_Name']:
                summary_df = pd.DataFrame(summary_data)
                summary_excel = create_excel_buffer(summary_df, 'Summary')
                zip_file.writestr("00_SUMMARY.xlsx", summary_excel)
                print(f"Added summary file with {len(summary_data['Subscriber_Name'])} entries")
        
        zip_content = zip_buffer.getvalue()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"all_subscribers_data_{timestamp}.zip"
        
        print(f"Created ZIP file '{zip_filename}' with {files_created} Excel files ({len(zip_content)} bytes)")
        
        # Create response with proper headers for ZIP file
        response = StreamingResponse(
            io.BytesIO(zip_content),
            media_type='application/zip',
            headers={
                "Content-Disposition": f"attachment; filename=\"{zip_filename}\"",
                "Content-Type": "application/zip",
                "Content-Length": str(len(zip_content))
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in download_all_by_subscribers_zip: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error creating ZIP file: {str(e)}")


# Debug endpoint to test ZIP creation
@app.get("/test-zip")
async def test_zip():
    """Test endpoint to verify ZIP file creation works"""
    if current_data is None:
        return {"error": "No data available"}
    
    try:
        import zipfile
        
        # Create a simple test ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add a simple text file
            zip_file.writestr("test.txt", "This is a test file")
            
            # Add a sample Excel file if data exists
            if current_data is not None:
                sample_df = current_data.head(5).copy()
                excel_content = create_excel_buffer(sample_df, 'Test')
                zip_file.writestr("sample_data.xlsx", excel_content)
        
        zip_content = zip_buffer.getvalue()
        
        return StreamingResponse(
            io.BytesIO(zip_content),
            media_type='application/zip',
            headers={
                "Content-Disposition": "attachment; filename=\"test.zip\"",
                "Content-Type": "application/zip"
            }
        )
        
    except Exception as e:
        return {"error": f"ZIP test failed: {str(e)}"}



#download individual instead of zip 

@app.get("/download-all-subscribers-individually")
async def download_all_subscribers_individually():
    """Get list of all subscribers for individual downloads"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    try:
        df = current_data.copy()
        
        # Apply filtering for active users only
        if 'Is Open' in df.columns:
            filtered_df = df[df['Is Open'].astype(str).str.lower().isin(['yes', 'true', '1', 'active'])].copy()
        else:
            filtered_df = df.copy()
        
        if len(filtered_df) == 0:
            raise HTTPException(status_code=404, detail="No active users found")
        
        # Get unique subscribers with their record counts
        subscriber_stats = filtered_df.groupby('Subscriber Name').size().reset_index(name='record_count')
        subscriber_stats = subscriber_stats.sort_values('Subscriber Name')
        
        subscribers_list = []
        for _, row in subscriber_stats.iterrows():
            subscribers_list.append({
                "name": row['Subscriber Name'],
                "record_count": int(row['record_count']),
                "download_url": f"/download-subscriber-by-name?subscriber_name={row['Subscriber Name']}",
                "safe_filename": f"{create_safe_filename(row['Subscriber Name'])}.xlsx"
            })
        
        return {
            "total_subscribers": len(subscribers_list),
            "total_records": len(filtered_df),
            "subscribers": subscribers_list,
            "message": "Use the download_url for each subscriber to download individual files"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting subscribers: {str(e)}")
    




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

@app.get("/test-download")
async def test_download():
    """Test endpoint to check if basic download functionality works"""
    if current_data is None:
        return {"error": "No data available", "message": "Please upload a file first"}
    
    df = current_data.copy()
    
    try:
        # Create Excel file using helper function
        excel_content = create_excel_buffer(df, 'Test_Data')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"test_download_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"Error in test_download: {e}")
        return {"error": str(e), "message": "Error creating test download"}

@app.get("/debug-data")
async def debug_data():
    """Debug endpoint to check data structure and column values"""
    if current_data is None:
        return {"error": "No data available"}
    
    df = current_data
    
    debug_info = {
        "total_records": len(df),
        "columns": df.columns.tolist(),
        "data_types": df.dtypes.to_dict(),
        "sample_data": df.head(3).to_dict('records') if len(df) > 0 else [],
    }
    
    # Check specific columns
    if 'Is Open' in df.columns:
        debug_info['is_open_values'] = df['Is Open'].value_counts().to_dict()
        debug_info['is_open_unique'] = df['Is Open'].unique().tolist()
    
    if 'Subscriber Name' in df.columns:
        debug_info['subscriber_count'] = df['Subscriber Name'].nunique()
        debug_info['sample_subscribers'] = df['Subscriber Name'].dropna().unique()[:5].tolist()
    
    return debug_info

@app.get("/stats")
async def get_stats():
    """Get basic statistics about the data"""
    if current_data is None:
        raise HTTPException(status_code=404, detail="No data available")
    
    df = current_data
    
    # Check if required columns exist before calculating stats
    active_users = 0
    inactive_users = 0
    users_need_password_change = 0
    
    if 'Is Open' in df.columns:
        # Handle different possible values for Is Open
        is_open_values = df['Is Open'].astype(str).str.lower()
        active_users = len(df[is_open_values.isin(['yes', 'true', '1', 'active'])])
        inactive_users = len(df[is_open_values.isin(['no', 'false', '0', 'inactive'])])
    
    if 'Needs To Change Password' in df.columns:
        password_values = df['Needs To Change Password'].astype(str).str.lower()
        users_need_password_change = len(df[password_values.isin(['yes', 'true', '1'])])
    
    # Stats for download all (filtered data)
    try:
        filtered_for_download = filter_dataframe_for_download_all(df)
        download_all_records = len(filtered_for_download)
        download_all_subscribers = filtered_for_download['Subscriber Name'].nunique() if 'Subscriber Name' in filtered_for_download.columns and len(filtered_for_download) > 0 else 0
    except Exception as e:
        print(f"Error calculating download stats: {e}")
        download_all_records = 0
        download_all_subscribers = 0
    
    return {
        "total_records": len(df),
        "active_users": active_users,
        "inactive_users": inactive_users,
        "unique_subscribers": df['Subscriber Name'].nunique() if 'Subscriber Name' in df.columns else 0,
        "unique_branches": df['Branch Name'].nunique() if 'Branch Name' in df.columns else 0,
        "users_need_password_change": users_need_password_change,
        "filename": current_filename,
        "download_all_records": download_all_records,
        "download_all_subscribers": download_all_subscribers
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)