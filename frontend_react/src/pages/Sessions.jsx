import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Sessions = () => {
    const navigate = useNavigate();
    useEffect(() => {
        navigate('/chat');
    }, [navigate]);
    return null;
};

export default Sessions;
