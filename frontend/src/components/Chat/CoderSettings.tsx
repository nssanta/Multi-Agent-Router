import React from 'react';
import { Settings, GitBranch, Shield } from 'lucide-react';

interface CoderSettingsProps {
    settings: CoderConfig;
    onChange: (settings: CoderConfig) => void;
    disabled?: boolean;
}

export interface CoderConfig {
    use_tree_of_thoughts: boolean;
    num_branches: number;
    use_verifier: boolean;
    verifier_model_id?: string;
}

export const defaultCoderConfig: CoderConfig = {
    use_tree_of_thoughts: true,
    num_branches: 2,
    use_verifier: true,
    verifier_model_id: undefined,
};

export const CoderSettings: React.FC<CoderSettingsProps> = ({
    settings,
    onChange,
    disabled = false,
}) => {
    const handleChange = (key: keyof CoderConfig, value: any) => {
        onChange({ ...settings, [key]: value });
    };

    return (
        <div className="bg-dark-elevated rounded-lg p-4 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium text-dark-muted mb-2">
                <Settings size={16} />
                Coder Settings
            </div>

            {/* Tree of Thoughts */}
            <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={settings.use_tree_of_thoughts}
                        onChange={(e) => handleChange('use_tree_of_thoughts', e.target.checked)}
                        disabled={disabled}
                        className="w-4 h-4 rounded bg-dark-surface border-dark-border text-primary-500 focus:ring-primary-500"
                    />
                    <GitBranch size={16} className="text-primary-400" />
                    <span className="text-sm">Tree of Thoughts</span>
                </label>

                {settings.use_tree_of_thoughts && (
                    <div className="ml-6">
                        <label className="text-xs text-dark-muted block mb-1">
                            Количество веток
                        </label>
                        <input
                            type="number"
                            min={2}
                            max={5}
                            value={settings.num_branches}
                            onChange={(e) => handleChange('num_branches', parseInt(e.target.value) || 2)}
                            disabled={disabled}
                            className="input w-20 text-center text-sm"
                        />
                    </div>
                )}
            </div>

            {/* Verifier */}
            <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={settings.use_verifier}
                        onChange={(e) => handleChange('use_verifier', e.target.checked)}
                        disabled={disabled}
                        className="w-4 h-4 rounded bg-dark-surface border-dark-border text-green-500 focus:ring-green-500"
                    />
                    <Shield size={16} className="text-green-400" />
                    <span className="text-sm">Верификация кода</span>
                </label>

                {settings.use_verifier && (
                    <p className="text-xs text-dark-muted ml-6">
                        Проверка синтаксиса, безопасности и логики
                    </p>
                )}
            </div>

            {/* Info */}
            <div className="text-xs text-dark-muted border-t border-dark-border pt-3">
                <p>
                    <strong>Tree of Thoughts:</strong> генерирует несколько вариантов решения и выбирает лучший.
                </p>
                <p className="mt-1">
                    <strong>Верификатор:</strong> проверяет код на ошибки перед ответом.
                </p>
            </div>
        </div>
    );
};
