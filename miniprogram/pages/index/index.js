// 贡柑病虫害检测 — 主页面逻辑
const config = require('../../utils/config');

Page({
    data: {
        previewPath: '',     // 选中的图片临时路径
        loading: false,      // 加载中
        showResult: false,   // 显示结果

        // 模型选择
        models: [],          // [{name, description, num_classes, labels}]
        modelNames: [],      // picker 所用的名称列表
        modelIndex: 0,       // 当前选中的模型索引
        currentModel: 'mixed',

        // 结果
        result: {},
        resultIcon: '🔬',
        confPct: 0,
        confColor: '#22c55e',
        severityClass: '',
        severityLabel: '',

        // tips
        tipsLabels: '加载中...',
    },

    onLoad() {
        this.loadModels();
    },

    /* ── 加载模型列表 ── */
    loadModels() {
        wx.request({
            url: config.serverUrl + '/models',
            method: 'GET',
            success: (res) => {
                const models = res.data;
                this.setData({
                    models,
                    modelNames: models.map(m => m.description || m.name),
                    tipsLabels: this._formatTips(models[0]),
                });
            },
            fail: () => {
                // 兜底，不影响核心功能
                this.setData({ tipsLabels: '柑橘虫害 · 柑橘结痂 · 柑橘溃疡病 · 柑橘煤烟病 · 柑橘叶矿蛾 · 柑橘印度教螨 · 黑斑病 · 黄龙病 · 健康' });
            },
        });
    },

    onModelChange(e) {
        const idx = parseInt(e.detail.value);
        const model = this.data.models[idx];
        this.setData({
            modelIndex: idx,
            currentModel: model ? model.name : 'mixed',
            tipsLabels: model ? this._formatTips(model) : '',
        });
    },

    _formatTips(model) {
        if (!model || !model.labels) return '';
        const unique = [...new Set(model.labels)].slice(0, 10);
        const more = model.labels.length > 10 ? ` 等 ${model.labels.length} 类` : '';
        return unique.join(' · ') + more;
    },

    /* ── 选图 ── */
    chooseImage() {
        wx.chooseMedia({
            count: 1,
            mediaType: ['image'],
            sourceType: ['album', 'camera'],
            sizeType: ['compressed'],
            maxDuration: 30,
            camera: 'back',
            success: (res) => {
                this.setData({
                    previewPath: res.tempFiles[0].tempFilePath,
                    showResult: false,
                });
            },
        });
    },

    /* ── 识别 ── */
    doPredict() {
        if (!this.data.previewPath) {
            wx.showToast({ title: '请先拍照或选图', icon: 'none' });
            return;
        }

        this.setData({ loading: true, showResult: false });

        wx.uploadFile({
            url: config.serverUrl + '/predict',
            filePath: this.data.previewPath,
            name: 'image',
            formData: {
                model: this.data.currentModel,
            },
            success: (res) => {
                try {
                    const result = JSON.parse(res.data);
                    if (result.error) {
                        this._showError(result.error);
                        return;
                    }
                    this._renderResult(result);
                } catch (e) {
                    this._showError('识别结果解析失败，请重试');
                }
            },
            fail: () => {
                this._showError('网络异常，请检查连接后重试');
            },
            complete: () => {
                this.setData({ loading: false });
            },
        });
    },

    _renderResult(result) {
        const severityMap = {
            destructive: { cls: 'severity-destructive', label: '毁灭性病害' },
            severe:      { cls: 'severity-severe',      label: '严重病害' },
            common:      { cls: 'severity-common',      label: '常见病害' },
            healthy:     { cls: 'severity-healthy',     label: '健康' },
        };
        const sev = severityMap[result.severity] || { cls: '', label: result.severity || '' };

        const iconMap = {
            '黄龙病': '🟡', '溃疡病': '🟠', '黑斑病': '⚫',
            '炭疽病': '🟤', '健康':   '🌿', '柑橘虫害': '🐛',
            '柑橘煤烟病': '⬛', '柑橘叶矿蛾': '🦋', '柑橘印度教螨': '🕷️',
            '柑橘结痂': '🔶',
        };

        const conf = Math.round((result.confidence || 0) * 100);
        let confColor = '#22c55e';
        if (conf < 60) confColor = '#ef4444';
        else if (conf < 85) confColor = '#f97316';

        // 匹配图标：从 class_name 中提取基础病名（如 "黄龙病（叶片）" → "黄龙病"）
        const baseName = (result.class_name || '').replace(/（.+）/, '');
        const icon = iconMap[baseName] || iconMap[result.class_name] || '🔬';

        this.setData({
            showResult: true,
            result,
            resultIcon: icon,
            confPct: conf,
            confColor,
            severityClass: sev.cls,
            severityLabel: sev.label,
        });
    },

    _showError(msg) {
        wx.showModal({
            title: '识别出错了',
            content: msg,
            showCancel: false,
        });
    },

    /* ── 重置 ── */
    reset() {
        this.setData({
            previewPath: '',
            showResult: false,
            result: {},
        });
    },
});
