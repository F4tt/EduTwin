import React from 'react';
import ReactMarkdown from 'react-markdown';
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

/**
 * Markdown với support cho LaTeX math
 * Inline: $x^2 + y^2 = z^2$
 * Block: $$\int_a^b f(x) dx$$
 */
const MarkdownWithMath = ({ content }) => {
  // Preprocess content to extract and replace math with placeholders
  const preprocessMath = (text) => {
    const mathBlocks = [];
    let processedText = text;

    // Extract block math first ($$...$$)
    processedText = processedText.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
      const index = mathBlocks.length;
      mathBlocks.push({ type: 'block', math: math.trim() });
      return `<<<MATH_BLOCK_${index}>>>`;
    });

    // Extract inline math ($...$)
    processedText = processedText.replace(/\$([^$\n]+?)\$/g, (match, math) => {
      const index = mathBlocks.length;
      mathBlocks.push({ type: 'inline', math: math.trim() });
      return `<<<MATH_INLINE_${index}>>>`;
    });

    return { processedText, mathBlocks };
  };

  const { processedText, mathBlocks } = preprocessMath(content);

  // Custom renderer to restore math components
  const components = {
    p: ({ children }) => {
      const processChildren = (child) => {
        if (typeof child === 'string') {
          // Replace placeholders with actual math components
          const parts = [];
          let remaining = child;
          let key = 0;

          // Match block math placeholders
          const blockRegex = /<<<MATH_BLOCK_(\d+)>>>/g;
          let lastIndex = 0;
          let match;

          while ((match = blockRegex.exec(child)) !== null) {
            if (match.index > lastIndex) {
              parts.push(child.substring(lastIndex, match.index));
            }
            const blockIndex = parseInt(match[1]);
            const mathBlock = mathBlocks[blockIndex];
            parts.push(
              <div key={`block-${key++}`} style={{ margin: '12px 0' }}>
                <BlockMath math={mathBlock.math} />
              </div>
            );
            lastIndex = match.index + match[0].length;
          }

          if (lastIndex < child.length) {
            remaining = child.substring(lastIndex);
          } else {
            remaining = '';
          }

          // Match inline math placeholders in remaining text
          const inlineRegex = /<<<MATH_INLINE_(\d+)>>>/g;
          lastIndex = 0;

          while ((match = inlineRegex.exec(remaining)) !== null) {
            if (match.index > lastIndex) {
              parts.push(remaining.substring(lastIndex, match.index));
            }
            const inlineIndex = parseInt(match[1]);
            const mathBlock = mathBlocks[inlineIndex];
            parts.push(
              <InlineMath key={`inline-${key++}`} math={mathBlock.math} />
            );
            lastIndex = match.index + match[0].length;
          }

          if (lastIndex < remaining.length) {
            parts.push(remaining.substring(lastIndex));
          }

          return parts.length > 0 ? parts : child;
        }
        return child;
      };

      const processed = React.Children.map(children, processChildren);
      return <p>{processed}</p>;
    },
    
    text: ({ value }) => {
      // Process text nodes directly
      if (typeof value === 'string') {
        const parts = [];
        let remaining = value;
        let key = 0;

        // Block math
        const blockRegex = /<<<MATH_BLOCK_(\d+)>>>/g;
        let lastIndex = 0;
        let match;

        while ((match = blockRegex.exec(value)) !== null) {
          if (match.index > lastIndex) {
            parts.push(value.substring(lastIndex, match.index));
          }
          const blockIndex = parseInt(match[1]);
          const mathBlock = mathBlocks[blockIndex];
          parts.push(
            <div key={`block-${key++}`} style={{ margin: '12px 0' }}>
              <BlockMath math={mathBlock.math} />
            </div>
          );
          lastIndex = match.index + match[0].length;
        }

        if (lastIndex < value.length) {
          remaining = value.substring(lastIndex);
        } else {
          remaining = '';
        }

        // Inline math
        const inlineRegex = /<<<MATH_INLINE_(\d+)>>>/g;
        lastIndex = 0;

        while ((match = inlineRegex.exec(remaining)) !== null) {
          if (match.index > lastIndex) {
            parts.push(remaining.substring(lastIndex, match.index));
          }
          const inlineIndex = parseInt(match[1]);
          const mathBlock = mathBlocks[inlineIndex];
          parts.push(
            <InlineMath key={`inline-${key++}`} math={mathBlock.math} />
          );
          lastIndex = match.index + match[0].length;
        }

        if (lastIndex < remaining.length) {
          parts.push(remaining.substring(lastIndex));
        }

        return parts.length > 0 ? <>{parts}</> : value;
      }
      return value;
    },
    
    code: ({ node, inline, className, children, ...props }) => {
      // Don't process code blocks
      return inline ? (
        <code className={className} {...props}>
          {children}
        </code>
      ) : (
        <pre>
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      );
    }
  };

  return (
    <div className="markdown-with-math" style={{
      lineHeight: '1.6'
    }}>
      <ReactMarkdown components={components}>
        {processedText}
      </ReactMarkdown>
      
      <style>{`
        .markdown-with-math .katex {
          font-size: 1.05em;
        }
        
        .markdown-with-math .katex-display {
          margin: 16px 0;
          overflow-x: auto;
        }
        
        .markdown-with-math p {
          margin-bottom: 12px;
        }
        
        .markdown-with-math code {
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 0.9em;
        }
        
        .markdown-with-math pre {
          background: #f5f5f5;
          padding: 12px;
          border-radius: 6px;
          overflow-x: auto;
        }
        
        .markdown-with-math pre code {
          background: none;
          padding: 0;
        }
      `}</style>
    </div>
  );
};

export default MarkdownWithMath;
