window.addEventListener('load', () => {
  window.ui = SwaggerUIBundle({
    url: '/openapi.json',
    dom_id: '#swagger-ui',
    deepLinking: true,
    filter: true,
    docExpansion: 'none',
    displayRequestDuration: true,
    persistAuthorization: false,
    queryConfigEnabled: false,
    validatorUrl: null,
    withCredentials: false,
    tryItOutEnabled: false,
    presets: [SwaggerUIBundle.presets.apis],
  })
})
