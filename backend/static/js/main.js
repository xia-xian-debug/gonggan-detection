/* ============================================================
   贡柑病虫害检测系统 — 前端主逻辑
   功能：拍照/选图 → 上传 → 加载动画 → 结果展示 → 再拍一张
   ============================================================ */

(function () {
    'use strict';

    /* ── DOM 元素引用 ── */
    const $ = (sel) => document.querySelector(sel);

    // 视图
    const cameraView   = $('#cameraView');
    const resultView   = $('#resultView');
    const errorView    = $('#errorView');

    // 拍照页元素
    const uploadArea   = $('#uploadArea');
    const uploadPlaceholder = $('#uploadPlaceholder');
    const previewImage = $('#previewImage');
    const retakeHint   = $('#retakeHint');
    const fileInput    = $('#fileInput');
    const btnCamera    = $('#btnCamera');
    const btnGallery   = $('#btnGallery');
    const btnAnalyze   = $('#btnAnalyze');

    // 结果页元素
    const resultHeader     = $('#resultHeader');
    const resultIcon       = $('#resultIcon');
    const resultDisease    = $('#resultDisease');
    const confidenceFill   = $('#confidenceFill');
    const confidenceText   = $('#confidenceText');
    const resultDesc       = $('#resultDescription');
    const resultSymptoms   = $('#resultSymptoms');
    const resultTreatment  = $('#resultTreatment');
    const resultPesticides = $('#resultPesticides');
    const pesticideSection = $('#pesticideSection');
    const severityTag      = $('#severityTag');
    const btnBack          = $('#btnBack');
    const btnShare         = $('#btnShare');

    // 错误页
    const errorMessage = $('#errorMessage');
    const btnRetry     = $('#btnRetry');

    // 加载遮罩
    const loadingOverlay = $('#loadingOverlay');
    const loadingText    = $('#loadingText');

    // 模型选择器
    const modelSelector  = $('#modelSelector');
    const modelSelect    = $('#modelSelect');
    const tipsSupport    = $('#tipsSupport');

    // 反馈区
    const feedbackInput  = $('#feedbackInput');
    const btnFeedback    = $('#btnFeedback');
    const feedbackThanks = $('#feedbackThanks');

    /* ── 状态 ── */
    let selectedFile = null;
    let currentModel = 'mixed';
    let lastResult = null;   // 最近一次预测结果
    let lastImage = null;    // 最近一次上传的图片文件

    /* ═══════════════════════════════════════════════════════
       工具函数
       ═══════════════════════════════════════════════════════ */

    /** 切换视图 */
    function showView(view) {
        [cameraView, resultView, errorView].forEach(v => v.classList.remove('view--active'));
        view.classList.add('view--active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /** 🆕 加载可用模型列表 */
    async function loadModels() {
        try {
            const resp = await fetch('/models');
            const models = await resp.json();

            // 缓存模型数据，供切换时更新 tips
            window._models = models;

            // 只有一个模型 → 隐藏选择器，只更新 tips
            if (models.length <= 1) {
                modelSelector.style.display = 'none';
                updateTips(models[0]);
                return;
            }

            // 多个模型 → 显示下拉框
            modelSelector.style.display = 'block';
            modelSelect.innerHTML = '';
            models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.name;
                opt.textContent = `${m.description}（${m.num_classes} 类）`;
                modelSelect.appendChild(opt);
            });

            // 默认选中第一个，更新 tips
            currentModel = modelSelect.value;
            updateTips(models[0]);

            modelSelect.addEventListener('change', () => {
                currentModel = modelSelect.value;
                const selected = models.find(m => m.name === currentModel);
                if (selected) updateTips(selected);
            });
        } catch (err) {
            console.warn('加载模型列表失败:', err);
        }

    }

    /** 🆕 根据当前模型动态更新"支持识别"列表 */
    function updateTips(model) {
        if (!model || !model.labels) return;
        // 去重（混合模型叶片和果实的病名有重复）
        const unique = [...new Set(model.labels)];
        const names = unique.slice(0, 10);  // 最多显示 10 个
        const more = unique.length > 10 ? ` 等 ${unique.length} 类` : '';
        tipsSupport.innerHTML = `目前支持识别：<strong>${names.join(' · ')}${more}</strong>`;
    }

    /** 显示 Toast */
    function showToast(msg, duration = 2000) {
        let toast = $('.toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'toast';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.classList.add('toast--visible');

        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('toast--visible');
        }, duration);
    }

    /** 显示/隐藏加载层 */
    function showLoading(msg) {
        loadingText.textContent = msg || '正在分析叶片...';
        loadingOverlay.classList.add('loading-overlay--visible');
    }

    function hideLoading() {
        loadingOverlay.classList.remove('loading-overlay--visible');
    }

    /* ═══════════════════════════════════════════════════════
       图片选择逻辑
       ═══════════════════════════════════════════════════════ */

    /** 处理用户选中的图片文件 */
    function handleFile(file) {
        if (!file) return;

        // 校验文件类型
        const validTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            showToast('请选择 JPG / PNG / BMP / WebP 格式的图片');
            return;
        }

        // 校验文件大小（最大 10MB）
        if (file.size > 10 * 1024 * 1024) {
            showToast('图片大小不能超过 10MB');
            return;
        }

        selectedFile = file;

        // 预览
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            previewImage.style.display = 'block';
            uploadPlaceholder.style.display = 'none';
            retakeHint.style.display = 'block';
            btnAnalyze.style.display = 'flex';
        };
        reader.readAsDataURL(file);
    }

    /** 触发拍照 */
    function triggerCamera() {
        // capture="environment" 优先后置摄像头
        fileInput.setAttribute('capture', 'environment');
        fileInput.click();
    }

    /** 触发相册 */
    function triggerGallery() {
        fileInput.removeAttribute('capture');
        fileInput.click();
    }

    /* ═══════════════════════════════════════════════════════
       点击上传区域 → 重新选图
       ═══════════════════════════════════════════════════════ */
    uploadArea.addEventListener('click', () => {
        if (selectedFile) {
            // 已有图片 → 重新选择
            triggerCamera();
        }
    });

    /* ═══════════════════════════════════════════════════════
       文件选择变化
       ═══════════════════════════════════════════════════════ */
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        handleFile(file);
    });

    /* ═══════════════════════════════════════════════════════
       按钮事件
       ═══════════════════════════════════════════════════════ */

    btnCamera.addEventListener('click', triggerCamera);
    btnGallery.addEventListener('click', triggerGallery);

    /** 开始识别 */
    btnAnalyze.addEventListener('click', () => {
        if (!selectedFile) {
            showToast('请先拍摄或选择一张图片');
            return;
        }
        uploadAndPredict(selectedFile);
    });

    /** 返回拍照页 */
    btnBack.addEventListener('click', resetToCamera);

    /** 错误页重试按钮 */
    btnRetry.addEventListener('click', resetToCamera);

    /** 分享结果 */
    btnShare.addEventListener('click', () => {
        const disease = resultDisease.textContent;
        const confidence = confidenceText.textContent;
        const shareText = `🍊 贡柑病虫害检测结果：${disease}（${confidence}）——来自贡柑病虫害智能检测系统`;

        if (navigator.share) {
            navigator.share({
                title: '贡柑病虫害检测结果',
                text: shareText,
            }).catch(() => {
                // 用户取消分享，不处理
            });
        } else {
            // 降级：复制到剪贴板
            navigator.clipboard.writeText(shareText).then(() => {
                showToast('结果已复制到剪贴板');
            }).catch(() => {
                showToast('分享功能暂不可用');
            });
        }
    });

    /* ═══════════════════════════════════════════════════════
       核心：上传 + 预测
       ═══════════════════════════════════════════════════════ */

    async function uploadAndPredict(file) {
        showLoading('正在分析叶片...');

        const formData = new FormData();
        formData.append('image', file);
        // 🆕 如果用户选了非默认模型，也传过去
        if (currentModel && currentModel !== 'mixed') {
            formData.append('model', currentModel);
        }

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`服务器响应异常 (${response.status})`);
            }

            const result = await response.json();

            // 检查是否有错误
            if (result.error) {
                throw new Error(result.error);
            }

            // 模拟一个短暂延迟，让加载动画更自然
            await sleep(600);

            hideLoading();
            lastResult = result;   // 保存结果供反馈使用
            lastImage = file;      // 保存图片供反馈使用
            renderResult(result);
            resetFeedback();       // 重置反馈区

        } catch (err) {
            hideLoading();
            console.error('识别失败:', err);
            errorMessage.textContent = err.message || '网络异常或服务器未响应，请稍后重试';
            showView(errorView);
        }
    }

    /* ═══════════════════════════════════════════════════════
       结果渲染
       ═══════════════════════════════════════════════════════ */

    function renderResult(data) {
        const {
            class_id,
            class_name,
            confidence,
            description,
            symptoms,
            treatment,
            pesticides,
            severity,
        } = data;

        // 病害图标映射
        const iconMap = {
            '黄龙病': '🟡',
            '溃疡病': '🟠',
            '黑星病': '⚫',
            '炭疽病': '🟤',
            '健康':   '🟢',
        };

        // 严重程度映射
        const severityLabelMap = {
            'destructive': '毁灭性病害 ⚠️',
            'severe':      '严重病害 🔶',
            'common':      '常见病害',
            'healthy':     '健康 ✅',
        };
        const severityClassMap = {
            'destructive': 'severity--destructive',
            'severe':      'severity--severe',
            'common':      'severity--common',
            'healthy':     'severity--healthy',
        };

        // 填充数据
        resultIcon.textContent = iconMap[class_name] || '🔬';
        resultDisease.textContent = class_name || '未知';

        // 置信度进度条
        const pct = Math.round((confidence || 0) * 100);
        confidenceFill.style.width = pct + '%';
        confidenceText.textContent = '置信度 ' + pct + '%';

        // 置信度颜色
        confidenceFill.className = 'confidence-fill';
        if (pct >= 85) {
            confidenceFill.classList.add('confidence--high');
        } else if (pct >= 60) {
            confidenceFill.classList.add('confidence--mid');
        } else {
            confidenceFill.classList.add('confidence--low');
        }

        // 病害简介
        resultDesc.textContent = description || '暂无详细介绍';

        // 症状
        resultSymptoms.textContent = symptoms || '暂无特征描述';

        // 防治建议
        resultTreatment.innerHTML = '';
        const treatments = treatment || [];
        if (treatments.length === 0) {
            treatments.push('暂无防治建议');
        }
        treatments.forEach(t => {
            const li = document.createElement('li');
            li.textContent = t;
            resultTreatment.appendChild(li);
        });

        // 农药信息
        if (pesticides && pesticides.length > 0) {
            resultPesticides.innerHTML = '';
            pesticides.forEach(p => {
                const div = document.createElement('div');
                div.className = 'pesticide-card';
                div.innerHTML = `
                    <span class="pesticide-name">${p.name || ''}</span>
                    ${p.dilution ? `<span class="pesticide-info">稀释：${p.dilution}</span>` : ''}
                    ${p.timing ? `<span class="pesticide-info">｜喷施时间：${p.timing}</span>` : ''}
                `;
                resultPesticides.appendChild(div);
            });
            pesticideSection.style.display = 'block';
        } else {
            pesticideSection.style.display = 'none';
        }

        // 严重程度标签
        severityTag.textContent = severityLabelMap[severity] || severity || '';
        severityTag.className = 'severity-tag ' + (severityClassMap[severity] || '');

        // 健康状态的处理
        if (class_name === '健康') {
            resultIcon.textContent = '🌿';
            severityTag.textContent = '健康 ✅';
            severityTag.className = 'severity-tag severity--healthy';
        }

        // 切换到结果页
        showView(resultView);
    }

    /* ═══════════════════════════════════════════════════════
       重置到拍照状态
       ═══════════════════════════════════════════════════════ */

    function resetToCamera() {
        // 清空文件选择
        selectedFile = null;
        fileInput.value = '';

        // 重置预览
        previewImage.style.display = 'none';
        previewImage.src = '';
        uploadPlaceholder.style.display = '';
        retakeHint.style.display = 'none';
        btnAnalyze.style.display = 'none';

        // 切回拍照页
        showView(cameraView);
    }

    /* ═══════════════════════════════════════════════════════
       工具函数
       ═══════════════════════════════════════════════════════ */

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /* ═══════════════════════════════════════════════════════
       粘贴图片支持（桌面端调试用）
       ═══════════════════════════════════════════════════════ */

    document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        for (const item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                const file = item.getAsFile();
                handleFile(file);
                break;
            }
        }
    });

    /* ═══════════════════════════════════════════════════════
       拖拽图片支持（桌面端调试用）
       ═══════════════════════════════════════════════════════ */

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--green-500)';
        uploadArea.style.background = 'var(--green-100)';
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'var(--green-200)';
        uploadArea.style.background = 'var(--green-50)';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--green-200)';
        uploadArea.style.background = 'var(--green-50)';

        const file = e.dataTransfer?.files?.[0];
        if (file) handleFile(file);
    });

    /* ═══════════════════════════════════════════════════════
       农户反馈
       ═══════════════════════════════════════════════════════ */

    function resetFeedback() {
        feedbackThanks.style.display = 'none';
        feedbackInput.style.display = '';
        btnFeedback.style.display = '';
        feedbackInput.value = '';
    }

    btnFeedback.addEventListener('click', async () => {
        const correction = feedbackInput.value.trim();
        if (!correction) {
            showToast('请输入正确的病虫害名称');
            return;
        }
        if (!lastResult || !lastImage) {
            showToast('请先识别一张图片');
            return;
        }

        const formData = new FormData();
        formData.append('image', lastImage);
        formData.append('correction', correction);
        formData.append('result', JSON.stringify(lastResult));
        formData.append('notes', '');

        try {
            const resp = await fetch('/feedback', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.ok) {
                feedbackInput.style.display = 'none';
                btnFeedback.style.display = 'none';
                feedbackThanks.style.display = 'block';
            } else {
                showToast(data.error || '提交失败');
            }
        } catch (err) {
            showToast('网络异常，反馈提交失败');
        }
    });

    // ── 启动：加载模型列表 ──
    loadModels();
    console.log('🍊 贡柑病虫害检测系统 — 前端已就绪');
})();
