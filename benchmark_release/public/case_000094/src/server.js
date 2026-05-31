const app = require('./app/app');
const port = process.env.PORT || 9000;

app.listen(port, () => {
  console.log(`AstroSSR listening on port ${port}`);
});