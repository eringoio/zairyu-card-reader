# インストール

**[English version →](installation.md)**

方法は2つあります。多くの方は最初の方法で十分です。

---

## 担当者の方: 配布用 Windows パッケージ

1. `zairyu-reader` フォルダーを PC にコピーします。
2. Windows が自動で導入していない場合は、NFC リーダーのドライバーをインストールします。
3. `zairyu-reader.exe` をダブルクリックします。
4. 開いた画面で使用するリーダーを選び、保存を押します。

Python は不要です。システム全体へのインストールも行いません。設定は
`%APPDATA%\ZairyuReader\config.json` に保存され、内容はリーダー番号のみです。

**インターネット接続は不要です。** OCRモデルと証明書はパッケージに含まれています。

---

## 動作要件

### Windows

| バージョン | 状況 |
|---|---|
| Windows 11（64ビット） | 対応 |
| Windows 10（64ビット） | 対応 |
| Windows Server 2016（**デスクトップ エクスペリエンス**） | Chromium アプリモードで対応 |
| Windows Server Core | **非対応** — デスクトップUIを表示できません |

### カードリーダー

**ISO/IEC 14443 Type B に対応した PC/SC 非接触リーダー**が必要です。ここが最も間違えやすい点です。

在留カードは非接触の Type B（JIS X 6322-B）です。FeliCa、MIFARE、Type A、または一般的な
NFC タグの読み取りにしか対応していないリーダーでは**動作しません**。カードを差し込む接触式の
リーダーでも動作しません。Windows 上で `Alcorlink USB Smart Card Reader` のように表示される
機器は、多くの場合、接触式リーダーです。

あわせて次が必要です。

- リーダーメーカーの PC/SC ドライバーがインストールされていること;
- **Windows の Smart Card サービス**（`SCardSvr`）が実行中であること（`services.msc` で確認）。

### 画面表示

本アプリは次のいずれかを使って専用ウィンドウを開きます。

1. **Microsoft Edge WebView2 ランタイム** — デスクトップ版 Windows で優先されます。
2. **インストール済みの Google Chrome / Microsoft Edge / Chromium** のアプリモード —
   Windows Server 2016 で優先され、WebView2 が起動できない場合にも自動的に使用されます。
3. 既定のブラウザー（最後の手段、`--browser`）。

WebView2 も Chromium 系ブラウザーも存在しない場合は、無言で失敗せず、明確なメッセージを表示します。

### Python（ソースから実行する場合のみ）

Python **3.11 以降**（64ビット）。配布パッケージでは不要です。

---

## ソースから実行する

```bash
git clone <repository-url>
cd zairyu-card-reader

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python tools\fetch_ocr_assets.py

python app.py
```

ブラウザーで `http://127.0.0.1:8787` を開きます。

サーバーのみではなくデスクトップシェルを起動する場合は、`python app.py` の代わりに
`python launch_reader.py` を実行します。

### OCRモデルの準備

`resources/ocr/ppocrv6/model.onnx` は 76 MB あるため、**Git では管理していません。**
次のとおり、最初に1回だけ配置します。

```bash
python tools\fetch_ocr_assets.py
```

Windows では次のコマンドでも同じことができます。

```powershell
powershell -ExecutionPolicy Bypass -File tools\fetch_ocr_assets.ps1
```

このツールは固定されたリビジョンをダウンロードし、モデル・メタデータ・生成された辞書の
すべてを、リポジトリに含まれる `resources/ocr/ppocrv6/manifest.json` と照合します。
一致しない場合は、差異のあるファイル名を示したうえで、何も配置しません。

**この手順を行わなくてもアプリは動作し、ICチップの項目は読み取れます。** OCR由来の氏名と
住所のみが「読み取れませんでした」と表示されます。

配置済みのファイルはいつでも次のコマンドで検証できます。

```bash
python tools\verify_ocr_assets.py
```

詳細は [ocr.md](ocr.md)（英語）をご覧ください。

---

## インターネット接続が必要な場面・不要な場面

| 作業 | インターネット |
|---|---|
| Python 依存ライブラリのインストール（ソースの場合のみ） | **必要（1回のみ）** |
| OCRモデルの取得（ソースの場合のみ） | **必要（1回のみ）** |
| 配布パッケージの初回起動 | 不要 |
| **カードの読み取り・署名検証・コピー** | **常に不要** |

セットアップ後、本アプリは外部への通信を一切行いません。行う通信は `127.0.0.1` 上にある
自分自身のヘルスチェックのみです。

---

## サーバーを公開しないでください

> **このサーバーを LAN、トンネル（ngrok、Cloudflare Tunnel など）、リバースプロキシ、
> コンテナのポート公開、公開ホストで公開しないでください。**

ローカルAPIは確認済みのカード情報を返しますが、**利用者認証はありません。** カードリーダーには
認証すべき利用者が存在しないためです。キーボードの前にいる人だけがアクセスできることを前提に
設計されています。

`--host` に指定できるのは `127.0.0.1`、`localhost`、`::1` のみです。それ以外の値は、
`--no-browser` を含むすべてのモードで、明確なエラーとともに拒否されます。回避して使う設定では
ありません。

同じ理由から、サーバーは `Host` ヘッダーの許可リストとプロセスごとのトークンも要求します。
これにより、たまたま開いた Web ページからアクセスされることもありません。詳細は
[privacy-and-security.md](privacy-and-security.md)（英語）をご覧ください。

---

## 起動モード

| コマンド | 動作 |
|---|---|
| `zairyu-reader.exe` | 通常。デスクトップ版 Windows では WebView2、Server 2016 または WebView2 起動失敗時は Chromium アプリモード |
| `zairyu-reader.exe --webview` | WebView2 を強制。起動できない場合は明確に失敗します |
| `zairyu-reader.exe --chrome-app` | インストール済み Chromium のアプリモードを強制 |
| `zairyu-reader.exe --browser` | 最後の手段。既定のブラウザーで開きます |
| `zairyu-reader.exe --no-browser` | サーバーのみ（調査用）。`--headless` は互換用の別名で、ヘッドレス Chrome を起動するものでは**ありません** |

自動検出でブラウザーが見つからない場合は、`ZAIRYU_BROWSER_PATH` で実行ファイルを指定できます。

ポートの既定値は 8787 で、`--port` で変更できます。

---

## 動作確認

1. アドレスバーのないウィンドウが開くこと。
2. リーダー一覧に使用するリーダーが表示されること。
3. カードを置いた状態で **カードを確認** を押すと、カードが検出されること。
4. 「開発・テスト用サンプルデータを使う」にチェックを入れて1回読み取ると、17項目に明らかに
   合成とわかる値（`SAMPLE NAME`、`SAMPLELAND`）が入ること。実在のカードを使わずに、UIと
   コピー形式が正しく動くことを確認できます。

手順2または3が失敗する場合は [troubleshooting.md](troubleshooting.md)（英語）をご覧ください。
