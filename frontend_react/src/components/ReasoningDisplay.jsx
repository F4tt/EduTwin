import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Play, CheckCircle, Circle, XCircle, Brain, Minimize2, Maximize2 } from 'lucide-react';

const ReasoningDisplay = ({ steps = [], isProcessing = false, isCompleted = false, defaultCollapsed = false }) => {
  const [expandedSteps, setExpandedSteps] = useState(new Set());
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  // Auto-expand new steps when processing
  useEffect(() => {
    if (steps.length > 0 && !isCollapsed) {
      setExpandedSteps(prev => {
        const newSet = new Set(prev);
        newSet.add(steps.length - 1);
        return newSet;
      });
    }
  }, [steps.length, isCollapsed]);

  // DO NOT auto-collapse when completed - let user see the reasoning
  // User can manually collapse if they want

  const toggleStep = (index) => {
    setExpandedSteps(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const toggleCollapseAll = () => {
    setIsCollapsed(!isCollapsed);
  };

  if (!isProcessing && steps.length === 0) return null;

  // Count completed steps
  const completedSteps = steps.filter(s => s.status === 'completed').length;
  const totalSteps = steps.length;

  return (
    <div className="reasoning-container">
      {/* Collapsible Header */}
      <div 
        className="reasoning-header" 
        onClick={toggleCollapseAll}
        style={{ cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <Brain size={16} style={{ color: '#3b82f6' }} />
          <span className="reasoning-title">Quá trình suy luận</span>
          {totalSteps > 0 && (
            <span style={{ 
              fontSize: '0.75rem', 
              color: isCompleted ? '#10b981' : '#64748b',
              background: isCompleted ? '#dcfce7' : '#f1f5f9',
              padding: '2px 8px',
              borderRadius: '10px',
              fontWeight: '500'
            }}>
              {isCompleted ? `✓ Hoàn thành ${totalSteps} bước` : `${completedSteps}/${totalSteps} bước`}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isProcessing && (
            <div className="reasoning-loader">
              <div className="dot"></div>
              <div className="dot"></div>
              <div className="dot"></div>
            </div>
          )}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '4px',
            color: '#64748b',
            fontSize: '0.75rem'
          }}>
            {isCollapsed ? (
              <>
                <Maximize2 size={14} />
                <span>Mở rộng</span>
              </>
            ) : (
              <>
                <Minimize2 size={14} />
                <span>Thu gọn</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Collapsed Summary */}
      <AnimatePresence>
        {isCollapsed && totalSteps > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="reasoning-summary"
          >
            <div style={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              gap: '6px',
              padding: '8px 0'
            }}>
              {steps.map((step, index) => (
                <div 
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 8px',
                    background: step.status === 'completed' ? '#dcfce7' : step.status === 'executing' ? '#dbeafe' : '#f1f5f9',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    color: step.status === 'completed' ? '#166534' : step.status === 'executing' ? '#1d4ed8' : '#64748b'
                  }}
                >
                  {step.status === 'completed' ? (
                    <CheckCircle size={12} />
                  ) : step.status === 'executing' ? (
                    <Play size={12} />
                  ) : (
                    <Circle size={12} />
                  )}
                  <span>{step.tool_name || step.action || `Bước ${index + 1}`}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expanded Steps */}
      <AnimatePresence>
        {!isCollapsed && steps.map((step, index) => {
          const statusIcon = step.status === 'completed' ? (
            <CheckCircle size={14} style={{ color: '#10b981' }} />
          ) : step.status === 'executing' ? (
            <Play size={14} style={{ color: '#3b82f6' }} />
          ) : step.status === 'failed' ? (
            <XCircle size={14} style={{ color: '#ef4444' }} />
          ) : (
            <Circle size={14} style={{ color: '#94a3b8' }} />
          );
          
          return (
            <motion.div 
              key={index} 
              initial={{ opacity: 0, y: -10 }} 
              animate={{ opacity: 1, y: 0 }} 
              exit={{ opacity: 0, height: 0 }} 
              className="reasoning-step"
            >
              <div className="step-header" onClick={() => toggleStep(index)} style={{ cursor: 'pointer' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                  {statusIcon}
                  <span className="step-number">Bước {step.step || index + 1}</span>
                  {step.tool_name && (
                    <span style={{ color: '#3b82f6', fontSize: '0.85rem', fontWeight: '500' }}>
                      {step.tool_name}
                    </span>
                  )}
                  {step.description && (
                    <span style={{ color: '#64748b', fontSize: '0.85rem', marginLeft: '0.25rem' }}>
                      - {step.description}
                    </span>
                  )}
                </div>
                {expandedSteps.has(index) ? (
                  <ChevronDown size={16} style={{ color: '#64748b' }} />
                ) : (
                  <ChevronRight size={16} style={{ color: '#64748b' }} />
                )}
              </div>
              
              <AnimatePresence>
                {expandedSteps.has(index) && (
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }} 
                    animate={{ height: 'auto', opacity: 1 }} 
                    exit={{ height: 0, opacity: 0 }} 
                    className="step-content"
                  >
                    {step.tool_purpose && (
                      <div className="step-item" style={{ borderLeft: '3px solid #3b82f6', backgroundColor: '#eff6ff' }}>
                        <div className="item-label" style={{ color: '#3b82f6' }}>Mục đích</div>
                        <div className="item-content">{step.tool_purpose}</div>
                      </div>
                    )}
                    {step.thought && (
                      <div className="step-item thought">
                        <div className="item-label">Suy nghĩ</div>
                        <div className="item-content">{step.thought}</div>
                      </div>
                    )}
                    {step.action && (
                      <div className="step-item action">
                        <div className="item-label">Công cụ sử dụng</div>
                        <div className="item-content">
                          <span className="action-name">{step.action}</span>
                          {step.action_input && (
                            <div className="action-input">
                              <span className="label">Tham số:</span>
                              <code>{step.action_input}</code>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    {step.progressMessages && step.progressMessages.length > 0 && (
                      <div className="step-item progress">
                        <div className="item-label">Tiến độ</div>
                        <div className="item-content">
                          {step.progressMessages.map((msg, i) => (
                            <div 
                              key={i} 
                              style={{ 
                                marginBottom: '4px', 
                                color: msg.startsWith('✅') ? '#10b981' : msg.startsWith('❌') ? '#ef4444' : '#64748b' 
                              }}
                            >
                              {msg}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {step.observation && (
                      <div className="step-item observation">
                        <div className="item-label">
                          Kết quả{step.result_length && ` (${step.result_length} ký tự)`}
                        </div>
                        <div className="item-content">
                          <pre style={{ maxHeight: '200px', overflow: 'auto' }}>{step.observation}</pre>
                        </div>
                      </div>
                    )}
                    {step.result_preview && !step.observation && (
                      <div className="step-item observation">
                        <div className="item-label">Kết quả</div>
                        <div className="item-content">{step.result_preview}</div>
                      </div>
                    )}
                    {step.error && (
                      <div className="step-item" style={{ borderLeft: '3px solid #ef4444', backgroundColor: '#fef2f2' }}>
                        <div className="item-label" style={{ color: '#ef4444' }}>Lỗi</div>
                        <div className="item-content" style={{ color: '#ef4444' }}>{step.error}</div>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </AnimatePresence>

      <style>{`
        .reasoning-container {
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-left: 3px solid #3b82f6;
          border-radius: 8px;
          padding: 12px;
          margin: 12px 0;
          font-size: 13px;
        }
        .reasoning-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 4px 8px;
          margin-bottom: 8px;
          font-weight: 500;
          color: #475569;
          font-size: 13px;
          border-radius: 4px;
          transition: background 0.2s;
        }
        .reasoning-header:hover {
          background: #f1f5f9;
        }
        .reasoning-title {
          letter-spacing: .3px;
        }
        .reasoning-loader {
          display: flex;
          gap: 3px;
        }
        .reasoning-loader .dot {
          width: 5px;
          height: 5px;
          background: #3b82f6;
          border-radius: 50%;
          animation: bounce 1.4s infinite ease-in-out both;
        }
        .reasoning-loader .dot:nth-child(1) { animation-delay: -.32s; }
        .reasoning-loader .dot:nth-child(2) { animation-delay: -.16s; }
        @keyframes bounce {
          0%, 100%, 80% { transform: scale(0); }
          40% { transform: scale(1); }
        }
        .reasoning-summary {
          border-top: 1px solid #e2e8f0;
        }
        .reasoning-step {
          background: #fff;
          border-radius: 6px;
          margin-bottom: 6px;
          overflow: hidden;
          border: 1px solid #e2e8f0;
        }
        .step-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 12px;
          background: #fafafa;
          user-select: none;
          transition: background .2s;
        }
        .step-header:hover {
          background: #f1f5f9;
        }
        .step-number {
          font-weight: 600;
          color: #334155;
          font-size: 12px;
        }
        .step-content {
          padding: 12px;
          background: #fff;
          border-top: 1px solid #f1f5f9;
        }
        .step-item {
          margin-bottom: 10px;
          padding: 8px;
          border-radius: 4px;
          background: #fafafa;
        }
        .step-item:last-child {
          margin-bottom: 0;
        }
        .item-label {
          font-weight: 600;
          margin-bottom: 4px;
          color: #64748b;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: .5px;
        }
        .item-content {
          color: #475569;
          line-height: 1.5;
          font-size: 13px;
        }
        .thought .item-content {
          font-style: italic;
          color: #64748b;
        }
        .action-name {
          display: inline-block;
          background: #3b82f6;
          color: #fff;
          padding: 3px 10px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }
        .action-input {
          margin-top: 6px;
          padding: 6px 8px;
          background: #f8fafc;
          border-radius: 4px;
          border: 1px solid #e2e8f0;
        }
        .action-input .label {
          font-weight: 500;
          color: #64748b;
          margin-right: 6px;
          font-size: 11px;
        }
        .action-input code {
          background: #fff;
          padding: 2px 5px;
          border-radius: 3px;
          font-family: 'Courier New', monospace;
          font-size: 12px;
          color: #0f172a;
          border: 1px solid #e2e8f0;
        }
        .observation .item-content pre {
          background: #f8fafc;
          padding: 8px;
          border-radius: 4px;
          overflow-x: auto;
          white-space: pre-wrap;
          word-wrap: break-word;
          font-family: 'Courier New', monospace;
          font-size: 12px;
          color: #334155;
          margin: 0;
          border: 1px solid #e2e8f0;
        }
      `}</style>
    </div>
  );
};

export default ReasoningDisplay;
