#!/bin/bash

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 資料庫設定（從 .env 讀取或直接設定）
DB_NAME="oauthdb"
DB_USER="keyclock"
DB_HOST="localhost"
DB_PORT="5432"

echo -e "${YELLOW}⚠️  警告：即將清空所有資料表的資料！${NC}"
echo "資料庫: $DB_NAME"
echo ""
read -p "確定要繼續嗎？輸入 'yes' 確認: " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${RED}❌ 操作已取消${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}🗑️  正在清空資料表...${NC}"

# 執行 TRUNCATE
PGPASSWORD="Hoone@83551401" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- 停用外鍵檢查
SET session_replication_role = 'replica';

-- 清空所有資料表
TRUNCATE TABLE users CASCADE;
TRUNCATE TABLE subsystems CASCADE;

-- 恢復外鍵檢查
SET session_replication_role = 'origin';

-- 顯示結果
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 資料表已清空（結構保留）${NC}"
else
    echo ""
    echo -e "${RED}❌ 清空失敗${NC}"
    exit 1
fi