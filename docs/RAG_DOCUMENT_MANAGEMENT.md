# RAG Document Management Features

This document describes the new document management features added to the RAG system.

## Features Implemented

### 1. Document Listing
- **Backend**: Added `get_document_list()` method to `VectorStoreManager` that queries ChromaDB and groups chunks by source filename
- **API**: New `GET /documents` endpoint returns list of documents with chunk counts
- **Frontend**: Document Library section in sidebar displays all uploaded documents with their chunk counts

### 2. Document Deletion
- **Backend**: Added `delete_document_by_source()` method to `VectorStoreManager` that deletes all chunks for a given source filename
- **API**: New `DELETE /documents/{source_filename}` endpoint to delete specific documents
- **Frontend**: Delete button (🗑️) next to each document in the library for easy removal

### 3. Bulk Upload
- **Backend**: New `POST /upload-bulk` endpoint that accepts multiple files and processes them sequentially
- **API**: Returns detailed results for each file (success, skipped, or failed)
- **Frontend**: File uploader now accepts multiple files with detailed feedback on upload status

### 4. Duplicate Prevention
- **Backend**: Added `check_document_exists()` method to `VectorStoreManager`
- **Document Processor**: Enhanced metadata to include normalized filenames for duplicate detection
- **API**: Both single and bulk upload endpoints check for duplicates before processing
- **Frontend**: Clear error messages when attempting to upload duplicate files

## API Endpoints

### GET /documents
Returns list of all documents in the vector store.

**Response:**
```json
{
  "documents": [
    {
      "source": "filename.pdf",
      "chunk_count": 15
    }
  ],
  "total_documents": 1
}
```

### DELETE /documents/{source_filename}
Deletes all chunks associated with a source filename.

**Response:**
```json
{
  "success": true,
  "message": "Document 'filename.pdf' deleted successfully",
  "chunks_deleted": 15
}
```

### POST /upload-bulk
Upload multiple documents for RAG indexing.

**Request:** multipart/form-data with multiple files
**Response:**
```json
{
  "results": [
    {
      "filename": "file1.pdf",
      "success": true,
      "message": "Document uploaded and indexed successfully",
      "chunks_created": 10
    },
    {
      "filename": "file2.pdf",
      "success": false,
      "message": "Document already exists: file2.pdf",
      "chunks_created": 0
    }
  ],
  "total_uploaded": 1,
  "total_skipped": 1,
  "total_failed": 0
}
```

### POST /upload (Updated)
Single document upload now includes duplicate checking.

**Error Response (409 Conflict):**
```json
{
  "detail": "Document already exists: filename.pdf. Please delete the existing document first or use a different filename."
}
```

## Implementation Details

### Metadata Enhancement
Documents now include enhanced metadata:
- `source`: Original filename
- `upload_timestamp`: ISO format timestamp of when the document was uploaded
- `normalized_source`: Lowercase filename for duplicate detection

### ChromaDB Query Pattern
Documents are queried using ChromaDB's metadata filtering:
```python
collection = self.vectorstore._collection
results = collection.get(
    where={"source": filename},
    include=["metadatas"]
)
```

### Duplicate Detection Strategy
1. Filenames are normalized (lowercase) and stored in metadata
2. Before uploading, the system checks if any chunks exist with the same source filename
3. Single uploads reject duplicates with HTTP 409
4. Bulk uploads skip duplicates and report them in the response

## UI Features

### Document Library
Located in the sidebar below the upload section:
- Displays all uploaded documents
- Shows chunk count for each document
- Provides delete button for each document
- Includes refresh button to update the list

### Enhanced Upload
- Supports single or multiple file selection
- Shows detailed progress during bulk uploads
- Displays summary (uploaded, skipped, failed)
- Expandable details section shows per-file results

## Usage Examples

### Upload Multiple Documents
1. Click "Choose file(s)" in the sidebar
2. Select multiple PDF, TXT, or DOCX files
3. Click "Index Document(s)"
4. Review the upload summary and details

### View Uploaded Documents
The Document Library section automatically displays all uploaded documents with their chunk counts.

### Delete a Document
1. Find the document in the Document Library
2. Click the 🗑️ button next to the document
3. The document and all its chunks will be removed from the vector store

### Prevent Duplicates
The system automatically prevents duplicate uploads:
- Single upload: Returns error if document already exists
- Bulk upload: Skips duplicates and reports them

## Files Modified

1. **backend/rag/vectorstore.py**
   - Added `get_document_list()` method
   - Added `delete_document_by_source()` method
   - Added `check_document_exists()` method

2. **backend/rag/document_processor.py**
   - Enhanced `load_from_bytes()` to add timestamps and normalized filenames

3. **backend/api/routes.py**
   - Added `DocumentInfo`, `DocumentListResponse`, `BulkUploadResult`, `BulkUploadResponse` models
   - Added `GET /documents` endpoint
   - Added `DELETE /documents/{source_filename}` endpoint
   - Added `POST /upload-bulk` endpoint
   - Updated `POST /upload` with duplicate checking

4. **frontend/app.py**
   - Added `upload_documents_bulk()` helper function
   - Added `get_documents()` helper function
   - Added `delete_document()` helper function
   - Added `render_document_manager()` UI component
   - Updated file uploader to support multiple files
   - Enhanced upload handling with detailed feedback

## Testing Recommendations

1. **Test duplicate prevention**
   - Upload a document
   - Try uploading the same document again
   - Verify rejection/skip behavior

2. **Test bulk upload**
   - Select multiple files (mix of supported formats)
   - Verify all files are processed
   - Check detailed results

3. **Test document deletion**
   - Upload a document
   - Delete it from the library
   - Verify all chunks are removed
   - Confirm it no longer appears in queries

4. **Test document listing**
   - Upload several documents
   - Verify chunk counts are accurate
   - Refresh and verify consistency

## Future Enhancements

Potential improvements for future iterations:
- Search/filter documents in the library
- Sort documents by name, date, or chunk count
- Preview document content
- Batch delete multiple documents
- Document metadata editing
- Export document list

