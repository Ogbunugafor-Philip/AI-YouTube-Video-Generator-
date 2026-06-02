// PM2 process manager config for the AI YouTube Video Generator.
//
//   pm2 start ecosystem.config.js     # start under PM2 (autorestart on crash)
//   pm2 save                          # persist the process list
//   pm2 startup                       # generate the boot script (run once, follow its instructions)
//   pm2 logs vid-gen-api              # tail logs
//
// PM2 runs the venv's uvicorn directly (interpreter: 'none') and restarts it
// automatically if it crashes or the box reboots (with `pm2 startup` + save).

const PROJECT_ROOT = __dirname

module.exports = {
  apps: [
    {
      name: 'vid-gen-api',
      cwd: `${PROJECT_ROOT}/backend`,
      script: `${PROJECT_ROOT}/venv/bin/uvicorn`,
      args: 'main:app --host 0.0.0.0 --port 8003',
      interpreter: 'none', // script is an executable with its own shebang
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_restarts: 15,
      min_uptime: '10s',
      restart_delay: 3000,
      max_memory_restart: '1G',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      out_file: `${PROJECT_ROOT}/logs/api-out.log`,
      error_file: `${PROJECT_ROOT}/logs/api-error.log`,
      merge_logs: true,
      time: true,
    },
  ],
}
