// Document management utilities for structure reference documents
import axiosClient from './axiosClient';

/**
 * Upload a reference document for a structure
 */
export const uploadStructureDocument = async (structureId, file) => {
    const formData = new FormData();
    formData.append('structure_id', structureId);
    formData.append('file', file);
    formData.append('file_name', file.name);
    formData.append('file_type', file.name.split('.').pop());

    const response = await axiosClient.post('/developer/structure-documents/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    
    return response.data;
};

/**
 * Get all documents for a structure
 */
export const getStructureDocuments = async (structureId) => {
    const response = await axiosClient.get(`/developer/structure-documents/${structureId}`);
    return response.data;
};

/**
 * Delete a document
 */
export const deleteStructureDocument = async (docId) => {
    const response = await axiosClient.delete(`/developer/structure-documents/${docId}`);
    return response.data;
};

/**
 * Get full document content (for preview)
 */
export const getDocumentFullContent = async (docId) => {
    const response = await axiosClient.get(`/developer/structure-documents/${docId}/full`);
    return response.data;
};
