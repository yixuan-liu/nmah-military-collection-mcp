"use strict";
window.addEventListener("load", function () {
  window.ui = SwaggerUIBundle({
    spec: window.SMITHSONIAN_OPENAPI,
    dom_id: "#swagger-ui",
    presets: [SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
    deepLinking: true,
    filter: true,
    displayOperationId: true,
    displayRequestDuration: true,
    docExpansion: "list",
    defaultModelsExpandDepth: 0,
    validatorUrl: null,
    persistAuthorization: false,
    queryConfigEnabled: false,
    tryItOutEnabled: false,
    supportedSubmitMethods: ["get"],
    withCredentials: false
  });
});
