const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');

const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');

const dev = process.env.NODE_ENV !== 'production';
const hostname = '0.0.0.0';
const port = parseInt(process.env.PORT || '3000', 10);

console.log(`Starting Next.js server in ${dev ? 'development' : 'production'} mode`);
console.log(`Binding to ${hostname}:${port}`);

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

app.prepare()
  .then(() => {
    return new Promise((resolve, reject) => {
      const server = createServer(async (req, res) => {
        try {
          const parsedUrl = parse(req.url, true);
          await handle(req, res, parsedUrl);
        } catch (err) {
          console.error('Error occurred handling', req.url, err);
          res.statusCode = 500;
          res.end('internal server error');
        }
      });

      server.listen(port, hostname, (err) => {
        if (err) {
          console.error('Failed to start server:', err);
          reject(err);
          return;
        }
        console.log(`✅ Server ready on http://${hostname}:${port}`);
        resolve();
      });

      server.on('error', (err) => {
        console.error('Server error:', err);
        reject(err);
      });
    });
  })
  .catch((err) => {
    console.error('Failed to prepare Next.js app:', err);
    process.exit(1);
  });

