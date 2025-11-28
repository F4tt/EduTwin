export const STUDY_SCORES_UPDATED_EVENT = 'studyScoresUpdated';
export const ML_MODEL_CHANGED_EVENT = 'mlModelChanged';
export const ML_PARAMETERS_CHANGED_EVENT = 'mlParametersChanged';
export const REFERENCE_DATASET_CHANGED_EVENT = 'referenceDatasetChanged';
export const ML_PIPELINE_PROCESSING_EVENT = 'mlPipelineProcessing';
export const ML_PIPELINE_COMPLETED_EVENT = 'mlPipelineCompleted';

const getEventTarget = () => (typeof window !== 'undefined' ? window : null);

const dispatchAppEvent = (name, detail) => {
    const target = getEventTarget();
    if (!target) return;
    try {
        const event = detail === undefined ? new Event(name) : new CustomEvent(name, { detail });
        target.dispatchEvent(event);
    } catch (err) {
        console.error(`Failed to dispatch event ${name}`, err);
    }
};

export const emitStudyScoresUpdated = (detail) => dispatchAppEvent(STUDY_SCORES_UPDATED_EVENT, detail);
export const emitMlModelChanged = (detail) => dispatchAppEvent(ML_MODEL_CHANGED_EVENT, detail);
export const emitMlParametersChanged = (detail) => dispatchAppEvent(ML_PARAMETERS_CHANGED_EVENT, detail);
export const emitReferenceDatasetChanged = (detail) => dispatchAppEvent(REFERENCE_DATASET_CHANGED_EVENT, detail);
export const emitMlPipelineProcessing = (detail) => dispatchAppEvent(ML_PIPELINE_PROCESSING_EVENT, detail);
export const emitMlPipelineCompleted = (detail) => dispatchAppEvent(ML_PIPELINE_COMPLETED_EVENT, detail);

export const REFRESH_DATA_EVENTS = [
    STUDY_SCORES_UPDATED_EVENT,
    ML_MODEL_CHANGED_EVENT,
    ML_PARAMETERS_CHANGED_EVENT,
    REFERENCE_DATASET_CHANGED_EVENT,
    ML_PIPELINE_COMPLETED_EVENT,
];

// Export eventBus object for direct emit
export const eventBus = {
    emit: (eventName, detail) => dispatchAppEvent(eventName, detail),
    on: (eventName, handler) => {
        const target = getEventTarget();
        if (target) target.addEventListener(eventName, handler);
    },
    off: (eventName, handler) => {
        const target = getEventTarget();
        if (target) target.removeEventListener(eventName, handler);
    }
};
