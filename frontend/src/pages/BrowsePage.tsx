import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { FileBrowser } from '../components/Browse/FileBrowser';

export const BrowsePage: React.FC = () => {
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-dark-surface border-b border-dark-border px-6 py-4">
        <Link to="/" className="inline-flex items-center gap-2 text-dark-text hover:text-white transition-colors">
          <ArrowLeft size={20} />
          <span className="font-medium">Back to Chat</span>
        </Link>
      </div>

      {/* Browser */}
      <FileBrowser />
    </div>
  );
};
