# Smithsonian Open Access 的非官方 Swagger 参考

本页面由独立项目维护。接口以 [Smithsonian 官方 API 文档](https://edan.si.edu/openaccess/apidocs/)为准。

[English](../en/swagger-ui.md) · [API 与媒体指南](smithsonian-api-and-media.md)

从项目根目录启动静态文档服务。

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

打开[本地 Swagger UI](http://127.0.0.1:8765/reference/smithsonian/swagger/)。页面展示通用 Smithsonian API。浏览说明无需密钥；实际请求需在 **Authorize** 填入密钥，并取决于上游的浏览器跨域设置。Swagger 不读取项目的 `.env`。申请入口见 [Smithsonian EDAN](https://edan.si.edu/openaccess/signup/form/)。

规范与页面资源在 [Swagger 目录](../reference/smithsonian/swagger/) 中。修改规范后，从项目根目录重新生成并校验 JS 镜像。

```sh
node docs/reference/smithsonian/swagger/sync-spec.mjs
node docs/reference/smithsonian/swagger/sync-spec.mjs --check
```

API 来源、规范范围及资源许可见[英文维护说明](../en/swagger-ui.md)。
