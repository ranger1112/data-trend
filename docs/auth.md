# 管理端认证与权限

管理端使用配置型管理员账号和签名 Bearer token。

## 配置

- `DATA_TREND_ADMIN_USERNAME`：管理员用户名，默认 `admin`。
- `DATA_TREND_ADMIN_PASSWORD`：管理员密码，默认 `admin`，生产环境必须覆盖。
- `DATA_TREND_ADMIN_ROLE`：默认角色，支持 `readonly`、`reviewer`、`operator`。
- `DATA_TREND_AUTH_TOKEN_SECRET`：token 签名密钥，生产环境必须覆盖。
- `DATA_TREND_AUTH_TOKEN_TTL_SECONDS`：token 有效期，默认 86400 秒。

## 接口

- `POST /admin/auth/login`：登录并返回 `access_token`。
- `GET /admin/auth/me`：返回当前登录用户。

后续 `/admin/*` 接口需要请求头：

```http
Authorization: Bearer <access_token>
```

## 权限

- `readonly`：查看数据源、任务、监控、质量报告和发布记录。
- `reviewer`：包含 readonly，可审核、修改、发布、驳回数据。
- `operator`：包含 reviewer，可管理数据源、调度、采集任务和告警测试。
