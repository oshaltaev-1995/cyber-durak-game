const target = process.env['KIBA_API_PROXY_TARGET'] ?? 'http://localhost:8000';

module.exports = [
  {
    context: ['/api'],
    target,
    secure: false,
    changeOrigin: true,
  },
];
