# 开发机挂载部署机 Wiki（macOS）

## 1. 连接信息

| 项目 | 值 |
|---|---|
| 部署机 IP | `10.10.14.110` |
| NFS 导出目录 | `/Users/ea/wikis` |
| 开发机挂载目录 | `~/wikis` |
| NFS 协议 | NFSv3 / TCP |
| Wiki 实例 ID | `9D251D3F-7E38-4C39-9A42-D9DF51C9FBB6` |

部署机上的 `/Users/ea/wikis` 是唯一权威 Wiki 副本。开发机不得继续维护独立副本。

## 2. 挂载前处理本地 Wiki

如果开发机的 `~/wikis` 还是旧的本地副本，先将其保留为备份，避免挂载后旧目录被遮蔽：

```bash
if [ -d "$HOME/wikis" ] && [ -n "$(ls -A "$HOME/wikis" 2>/dev/null)" ]; then
  mv "$HOME/wikis" "$HOME/wikis.local-backup"
fi

mkdir -p "$HOME/wikis"
```

> 如果 `~/wikis.local-backup` 已存在，请先为旧备份改名，再执行上述命令。

## 3. 手动挂载测试

```bash
sudo mount_nfs \
  -o vers=3,tcp,resvport,rw \
  10.10.14.110:/Users/ea/wikis \
  "$HOME/wikis"
```

检查挂载状态：

```bash
mount | grep "$HOME/wikis"
```

检查唯一 Wiki 实例标识：

```bash
cat "$HOME/wikis/.wiki-instance"
```

应包含：

```text
WIKI_INSTANCE_ID="9D251D3F-7E38-4C39-9A42-D9DF51C9FBB6"
```

执行读写验证：

```bash
printf 'development-machine-nfs-test\n' > "$HOME/wikis/.dev-nfs-test"
cat "$HOME/wikis/.dev-nfs-test"
rm "$HOME/wikis/.dev-nfs-test"
```

如果以上命令全部成功，说明开发机已经可以通过 NFS 读写部署机 Wiki。

## 4. 配置开机自动挂载

如果刚才已手动挂载，先卸载：

```bash
sudo umount "$HOME/wikis"
```

创建直接映射文件 `/etc/auto_wikis`：

```bash
printf '%s\t-fstype=nfs,vers=3,tcp,resvport,rw\t%s\n' \
  "$HOME/wikis" \
  '10.10.14.110:/Users/ea/wikis' \
  | sudo tee /etc/auto_wikis >/dev/null

sudo chown root:wheel /etc/auto_wikis
sudo chmod 644 /etc/auto_wikis
```

把映射注册到 `/etc/auto_master`：

```bash
grep -q 'auto_wikis' /etc/auto_master || \
  printf '%s\n' '/- auto_wikis -nobrowse' \
  | sudo tee -a /etc/auto_master >/dev/null
```

重新加载自动挂载配置：

```bash
sudo automount -vc
```

访问目录以触发挂载：

```bash
ls "$HOME/wikis"
```

再次验证：

```bash
mount | grep "$HOME/wikis"
cat "$HOME/wikis/.wiki-instance"
```

## 5. 日常检查命令

检查 NFS 是否已挂载：

```bash
mount | grep '10.10.14.110:/Users/ea/wikis'
```

检查实例 ID：

```bash
grep '^WIKI_INSTANCE_ID=' "$HOME/wikis/.wiki-instance"
```

检查部署机导出是否可见：

```bash
showmount -e 10.10.14.110
```

预期导出目录：

```text
/Users/ea/wikis
```

## 6. 卸载命令

临时卸载：

```bash
sudo umount "$HOME/wikis"
```

如果普通卸载提示目录繁忙：

```bash
sudo diskutil unmount force "$HOME/wikis"
```

## 7. 故障检查

### 无法发现导出

```bash
ping 10.10.14.110
showmount -e 10.10.14.110
```

开发机必须位于部署机允许的 `10.10.14.0/23` 网段内。

### 提示权限不足

确认挂载参数包含：

```text
vers=3,tcp,resvport,rw
```

部署机已将 NFS 用户统一映射为 `ea:staff`（UID/GID `501:20`），不依赖开发机本地用户 UID 与部署机一致。

### 自动挂载未触发

```bash
sudo automount -vc
ls "$HOME/wikis"
mount | grep "$HOME/wikis"
```
