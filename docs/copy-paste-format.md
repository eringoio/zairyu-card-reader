# Copy/Paste Format

Each card has these 17 lines, always in this order: 在留カード番号, 氏名, 生年月日, 性別, 国籍・地域, 在留資格, 在留期間, 在留期限, カード有効期限, 許可日, 都道府県, 市区町村, 以降の住所, 就労制限, 資格外活動許可, 資格外活動許可の詳細, 署名検証. Each line is `label<TAB>value`, including blank values.

Multiple cards use `【在留カード 1/2】` headers with exactly one blank line between blocks. There is no JSON, metadata, timestamp, or technical material. Values are trimmed and tabs/newlines/control characters are replaced or removed. The exact fixtures are in the prompt pack.
