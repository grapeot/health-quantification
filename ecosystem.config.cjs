module.exports = {
  apps: [
    {
      name: "health-quant-backend",
      cwd: "/Users/grapeot/co/knowledge_working/adhoc_jobs/health_quantification",
      script: "scripts/start_backend.sh",
      interpreter: "bash",
      env: {
        HEALTH_QUANT_SERVER_HOST: "0.0.0.0",
        HEALTH_QUANT_SERVER_PORT: "7996",
      },
    },
  ],
};
