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
  if (!content) return null;

  // Preprocess content to extract and replace math with placeholders
  const mathBlocksRef = React.useRef([]);

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

    mathBlocksRef.current = mathBlocks;
    return processedText;
  };

  const processedText = preprocessMath(content);
  const mathBlocks = mathBlocksRef.current;

  // Helper function to process any text and replace math placeholders
  const replaceMathPlaceholders = (text, keyPrefix = '') => {
    if (typeof text !== 'string') return text;

    const parts = [];
    let remaining = text;
    let key = 0;
    let lastIndex = 0;

    // Combined regex for both block and inline math
    const mathRegex = /<<<MATH_(BLOCK|INLINE)_(\d+)>>>/g;
    let match;

    while ((match = mathRegex.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      const mathIndex = parseInt(match[2]);
      const mathBlock = mathBlocks[mathIndex];

      if (mathBlock) {
        if (match[1] === 'BLOCK') {
          parts.push(
            <div key={`${keyPrefix}block-${key++}`} style={{ margin: '12px 0' }}>
              <BlockMath math={mathBlock.math} />
            </div>
          );
        } else {
          parts.push(
            <InlineMath key={`${keyPrefix}inline-${key++}`} math={mathBlock.math} />
          );
        }
      } else {
        // If mathBlock not found, keep the original placeholder text
        parts.push(match[0]);
      }

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text after last match
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  // Recursive function to process React children
  const processChildren = (children, keyPrefix = '') => {
    return React.Children.map(children, (child, index) => {
      if (typeof child === 'string') {
        return replaceMathPlaceholders(child, `${keyPrefix}${index}-`);
      }
      if (React.isValidElement(child) && child.props.children) {
        return React.cloneElement(child, {
          ...child.props,
          children: processChildren(child.props.children, `${keyPrefix}${index}-`)
        });
      }
      return child;
    });
  };

  // Custom components that process math placeholders
  const createMathAwareComponent = (Component) => {
    return ({ children, ...props }) => {
      const processed = processChildren(children);
      return <Component {...props}>{processed}</Component>;
    };
  };

  const components = {
    p: createMathAwareComponent('p'),
    li: createMathAwareComponent('li'),
    td: createMathAwareComponent('td'),
    th: createMathAwareComponent('th'),
    strong: createMathAwareComponent('strong'),
    em: createMathAwareComponent('em'),
    span: createMathAwareComponent('span'),
    div: createMathAwareComponent('div'),
    blockquote: createMathAwareComponent('blockquote'),
    h1: createMathAwareComponent('h1'),
    h2: createMathAwareComponent('h2'),
    h3: createMathAwareComponent('h3'),
    h4: createMathAwareComponent('h4'),
    h5: createMathAwareComponent('h5'),
    h6: createMathAwareComponent('h6'),

    code: ({ node, inline, className, children, ...props }) => {
      // Don't process code blocks - keep them as-is
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
