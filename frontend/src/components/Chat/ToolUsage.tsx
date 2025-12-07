import React, { useState } from 'react';
import { FileText, Code, FolderOpen, Terminal, ChevronDown, ChevronUp } from 'lucide-react';
import type { ToolCall } from '../../types';

interface ToolUsageProps {
    toolCalls: ToolCall[];
}

export const ToolUsage: React.FC<ToolUsageProps> = ({ toolCalls }) => {
    const [isOpen, setIsOpen] = useState(false);

    if (!toolCalls || toolCalls.length === 0) return null;

    return (
        <div className="mb-4 border border-dark-border/50 rounded-lg overflow-hidden bg-dark-bg/30">
            {/* Header */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between px-3 py-2 bg-dark-surface/50 hover:bg-dark-surface transition-colors text-xs font-medium text-dark-muted"
            >
                <span className="flex items-center gap-2">
                    <Terminal size={14} className="text-orange-400" />
                    Использованные инструменты ({toolCalls.length})
                </span>
                {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {/* Content */}
            {isOpen && (
                <div className="p-2 space-y-2">
                    {toolCalls.map((call, index) => (
                        <div key={index} className="bg-dark-bg p-2 rounded border border-dark-border/30">
                            <ToolItem call={call} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const ToolItem: React.FC<{ call: ToolCall }> = ({ call }) => {
    const { tool, params } = call;

    // Custom rendering based on tool name
    switch (tool) {
        case 'write_file':
            return (
                <div className="flex items-start gap-2 text-xs">
                    <FileText size={14} className="mt-0.5 text-blue-400" />
                    <div>
                        <div className="font-semibold text-dark-text">Write File</div>
                        <div className="font-mono text-dark-muted mt-1">{params.path}</div>
                        <details className="mt-1">
                            <summary className="cursor-pointer text-dark-muted hover:text-dark-text transition-colors text-[10px]">Show content</summary>
                            <div className="mt-1 p-2 bg-dark-surface rounded font-mono text-[10px] whitespace-pre-wrap overflow-x-auto max-h-32">
                                {params.content}
                            </div>
                        </details>
                    </div>
                </div>
            );

        case 'read_file':
            return (
                <div className="flex items-center gap-2 text-xs">
                    <FileText size={14} className="text-green-400" />
                    <div>
                        <span className="font-semibold text-dark-text">Read File: </span>
                        <span className="font-mono text-dark-muted">{params.path}</span>
                    </div>
                </div>
            );

        case 'run_code':
            return (
                <div className="flex items-start gap-2 text-xs">
                    <Code size={14} className="mt-0.5 text-purple-400" />
                    <div className="w-full">
                        <div className="font-semibold text-dark-text">Execute Code</div>
                        <div className="mt-1 p-2 bg-dark-surface rounded font-mono text-[10px] border-l-2 border-purple-500 overflow-x-auto">
                            <pre>{params.code}</pre>
                        </div>
                    </div>
                </div>
            );

        case 'list_directory':
            return (
                <div className="flex items-center gap-2 text-xs">
                    <FolderOpen size={14} className="text-yellow-400" />
                    <div>
                        <span className="font-semibold text-dark-text">List Directory</span>
                        {params.path && <span className="font-mono text-dark-muted ml-1">({params.path})</span>}
                    </div>
                </div>
            );

        default:
            return (
                <div className="text-xs">
                    <div className="font-semibold text-dark-text mb-1">{tool}</div>
                    <pre className="font-mono text-[10px] text-dark-muted overflow-x-auto">
                        {JSON.stringify(params, null, 2)}
                    </pre>
                </div>
            );
    }
};
