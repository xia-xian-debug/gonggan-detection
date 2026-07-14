// 贡柑病虫害检测 — 微信小程序入口
App({
    onLaunch() {
        console.log('🍊 贡柑病虫害检测小程序启动');
    },
    globalData: {
        // 后端服务器地址
        // 开发时用 localhost（需在微信开发者工具中勾选「不校验合法域名」）
        // 部署后改为 ngrok 公网地址 或 学院服务器地址
        serverUrl: 'http://127.0.0.1:5000',
    },
});
