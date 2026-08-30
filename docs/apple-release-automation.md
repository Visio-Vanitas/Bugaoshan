# Apple 发布自动化

本 fork 每 15 分钟检查一次
[`The-Brotherhood-of-SCU/Bugaoshan`](https://github.com/The-Brotherhood-of-SCU/Bugaoshan)
的新 Release。GitHub Actions 不能直接订阅另一个仓库的 Release 事件，因此使用定时轮询；
发现多个待处理版本时，每次运行按发布时间处理最早的一个。

处理规则：

- 每个正式版和预发布版都构建 arm64 macOS DMG，使用 Developer ID 签名、Apple
  公证并 staple 后上传到本 fork 的同名 Release。上游 Release 正文使用按 tag 生成的
  固定链接指向该文件，因此无需授予本工作流上游仓库写权限。
- 只有正式版构建 iOS IPA。上传 App Store Connect 并等待处理后，将 build 加入当前的
  内部和外部测试组；外部组随后提交 Beta App Review。
- 不自动提交生产 App Store 上架审核，也不删除或强制过期旧的 TestFlight build。
- 初始基线是 v2.3.0（Release ID `370689291`），不会重新处理更早的版本。
- 可在 Actions 的 `Sync Apple releases` 页面手动指定 tag；`force` 用于覆盖 DMG 或
  重新执行 TestFlight 分发步骤。脚本会先查询现有 build，避免重复上传相同版本/build 号。

## 安全边界

无密钥构建与签名发布在不同 runner 中完成：

1. `build-unsigned` 检出上游 tag，执行 Flutter/Dart/CocoaPods 构建，但没有任何 Apple
   凭据或上游仓库写权限；checkout 后也不保留 GitHub 凭据。
2. `publish-dmg` 和 `publish-testflight` 只下载前一个任务生成的归档，以系统工具签名、
   公证和上传，不执行上游源码或构建脚本。
3. macOS 与 iOS 使用不同的 P12 Secret，使每个发布任务只能取得自己需要的签名身份。

此隔离可防止上游构建脚本直接读取私钥，但不能阻止上游 Release 包含恶意应用代码并被
自动签名。仓库所有者已明确接受：未来任何上游非草稿 Release tag 均可自动使用其组织
证书签名、公证并分发，且上游 Release 权限被滥用时，恶意代码也可能获得组织签名并进入
TestFlight。

## Actions Secrets

仓库需要以下 Secrets：

| Secret | 内容 |
| --- | --- |
| `MACOS_DEVELOPER_ID_P12_BASE64` | 仅含 Developer ID Application 私钥的 P12，经 Base64 编码 |
| `MACOS_DEVELOPER_ID_P12_PASSWORD` | 上述 P12 的导出密码 |
| `IOS_DISTRIBUTION_P12_BASE64` | 仅含 Apple Distribution 私钥的 P12，经 Base64 编码 |
| `IOS_DISTRIBUTION_P12_PASSWORD` | 上述 P12 的导出密码 |
| `APPLE_API_PRIVATE_KEY` | App Store Connect API 的 `.p8` 原文 |
| `APPLE_API_KEY_ID` | App Store Connect API Key ID |
| `APPLE_API_ISSUER_ID` | App Store Connect Issuer ID |
| `MACOS_DEVELOPER_ID_PROFILE_BASE64` | `Bugaoshan Developer ID` 描述文件，经 Base64 编码 |
| `IOS_APP_STORE_PROFILE_BASE64` | 主应用 App Store 描述文件，经 Base64 编码 |
| `IOS_WIDGET_APP_STORE_PROFILE_BASE64` | Widget App Store 描述文件，经 Base64 编码 |

仓库可以保持公开：Secrets 不会写入 Git 历史，工作流也不监听
`pull_request`/`pull_request_target`。签名材料只写入 GitHub 托管 runner 的临时目录；
任务结束时删除临时 Keychain。发布 fork Release 使用任务自带、仅限本仓库的
`GITHUB_TOKEN`，不保存个人 GitHub 令牌。
