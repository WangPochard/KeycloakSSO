"""
FastAPI 應用程式啟動腳本
支援多種啟動模式和資料庫管理
"""
import uvicorn
import sys
import os
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# 確保可以 import app
sys.path.insert(0, os.path.dirname(__file__))

def setup_logging():
    """
    全系統 logging 設定
    - 固定 log 目錄
    - 固定 DEBUG 等級
    - logging 失敗不影響服務啟動
    """
    try:
        base_dir = Path(__file__).resolve().parent
        log_dir_path = base_dir / "logs"
        log_dir_path.mkdir(exist_ok=True)

        today = datetime.now().strftime('%Y%m%d')
        log_file = log_dir_path / f'app_{today}.log'
        error_log_file = log_dir_path / f'error_{today}.log'

        level = logging.DEBUG  # 永遠最高層級

        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()

        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

        # File
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=10, encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Error only
        error_handler = RotatingFileHandler(
            error_log_file, maxBytes=10 * 1024 * 1024, backupCount=10, encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

        logging.getLogger('uvicorn').setLevel(logging.WARNING)
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)

        logging.getLogger(__name__).info("✅ Logging initialized (DEBUG, fixed config)")

    except Exception as e:
        # ⚠️ 關鍵：logging 壞掉也不能影響服務
        print("⚠️ Logging initialization failed, fallback to stdout")
        print(e)

def parse_args():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description='FastAPI SSO 主系統')
    
    parser.add_argument(
        '--mode', '-m',
        choices=['dev', 'prod'],
        default='dev',
        help='運行模式：dev (開發) 或 prod (正式)'
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='綁定的 host (預設: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8001,
        help='綁定的 port (預設: 8001)'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=4,
        help='Worker 數量 (僅正式環境，預設: 4)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['critical', 'error', 'warning', 'info', 'debug'],
        default='info',
        help='Log 層級 (預設: info)'
    )
    
    # 資料庫操作
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='初始化資料庫（建立表）'
    )
    
    parser.add_argument(
        '--drop-db',
        action='store_true',
        help='刪除所有資料表（危險！）'
    )
    
    parser.add_argument(
        '--reset-db',
        action='store_true',
        help='重置資料庫（刪除後重建）'
    )
    
    parser.add_argument(
        '--truncate-db',
        action='store_true',
        help='清空資料表內容（保留結構）'
    )
    
    return parser.parse_args()


def check_database_connection():
    logger = logging.getLogger(__name__)
    """檢查資料庫連接"""
    try:
        from app.database import engine
        
        with engine.connect() as conn:
            logger.info("資料庫連接成功")
            return True
    except Exception as e:
        logger.error(f"❌ 資料庫連接失敗: {e}")
        logger.error("\n請檢查：")
        logger.error("  1. PostgreSQL 是否正在運行")
        logger.error("  2. .env 中的 DATABASE_URL 是否正確")
        logger.error("  3. 資料庫 'oauthdb' 是否已建立")
        return False


def init_database():
    """初始化資料庫（建立表）"""
    logger.info("正在初始化資料庫...")
    try:
        from app.database import engine, Base
        from app.models import User, SubSystem
        
        Base.metadata.create_all(bind=engine)
        
        logger.info("資料庫初始化完成")
        logger.info("   ├─ users 表已建立")
        logger.info("   └─ subsystems 表已建立")
        
        return True
    except Exception as e:
        logger.error(f"❌ 資料庫初始化失敗: {e}")
        return False


def drop_database():
    """刪除所有資料表"""
    logger.warning("警告：即將刪除所有資料表（包含所有資料）！")
    logger.warning("這個操作無法復原！")
    # confirm = input("請輸入 'DROP ALL TABLES' 確認: ")
    
    # if confirm != 'DROP ALL TABLES':
    #     print("❌ 操作已取消")
    #     return False
    
    try:
        from app.database import engine, Base
        from app.models import User, SubSystem
        
        logger.info("\n正在刪除資料表...")
        
        # 刪除所有表
        Base.metadata.drop_all(bind=engine, checkfirst=False)
        
        logger.info("所有資料表已刪除")
        logger.info("   ├─ users 表已刪除")
        logger.info("   └─ subsystems 表已刪除")
        
        return True
    except Exception as e:
        logger.error(f"❌ 刪除失敗: {e}")
        return False


def truncate_database():
    """清空資料表內容（保留結構）"""
    logger.warning("警告：即將清空所有資料表的內容（保留表結構）！")
    # confirm = input("確定要繼續嗎？輸入 'yes' 確認: ")
    
    # if confirm.lower() != 'yes':
    #     print("❌ 操作已取消")
    #     return False
    
    try:
        from app.database import engine
        from sqlalchemy import text
        
        logger.info("\n正在清空資料表...")
        
        with engine.connect() as conn:
            # 停用外鍵檢查
            conn.execute(text("SET session_replication_role = 'replica';"))
            
            # 清空表
            conn.execute(text("TRUNCATE TABLE users CASCADE;"))
            conn.execute(text("TRUNCATE TABLE subsystems CASCADE;"))
            
            # 恢復外鍵檢查
            conn.execute(text("SET session_replication_role = 'origin';"))
            
            conn.commit()
        
        logger.info("資料表已清空（結構保留）")
        logger.info("   ├─ users 表已清空")
        logger.info("   └─ subsystems 表已清空")
        
        return True
    except Exception as e:
        logger.error(f"❌ 清空失敗: {e}")
        return False


def reset_database():
    """重置資料庫（刪除後重建）"""
    logger.info("⚠️  警告：即將重置資料庫（所有資料將遺失）！")
    # confirm = input("請輸入 'RESET' 確認: ")
    
    # if confirm != 'RESET':
    #     print("❌ 操作已取消")
    #     return False
    
    # 先刪除
    logger.info("\n步驟 1/2: 刪除現有資料表...")
    try:
        from app.database import engine, Base
        Base.metadata.drop_all(bind=engine)
        logger.info("資料表已刪除")
    except Exception as e:
        logger.error(f"❌ 刪除失敗: {e}")
        return False
    
    # 再建立
    logger.info("\n步驟 2/2: 重新建立資料表...")
    return init_database()


def main():
    """主函數"""
    setup_logging()
    logger = logging.getLogger(__name__)
    args = parse_args()
    
    logger.info("=" * 70)
    logger.info("FastAPI SSO 主系統啟動中...")
    logger.info("=" * 70)
    
    # 檢查資料庫連接
    if not check_database_connection():
        sys.exit(1)
    
    
    # ========== 資料庫操作 ==========
    
    # 刪除資料表
    if args.drop_db:
        if drop_database():
            logger.info("\n操作完成")
        else:
            logger.error("\n❌ 操作失敗")
        sys.exit(0)
    
    # 清空資料表
    if args.truncate_db:
        if truncate_database():
            logger.info("\n操作完成")
        else:
            logger.error("\n❌ 操作失敗")
        sys.exit(0)
    
    # 重置資料庫
    if args.reset_db:
        if reset_database():
            logger.info("\n資料庫已重置")
        else:
            logger.error("\n❌ 重置失敗")
            sys.exit(1)
        
        # 詢問是否繼續啟動
        # start = input("\n是否啟動應用程式？(y/n): ")
        # if start.lower() != 'y':
        #     sys.exit(0)
    
    # 初始化資料庫
    if args.init_db:
        if not init_database():
            sys.exit(1)
    
    # ========== 啟動應用程式 ==========
    
    logger.info("=" * 70)
    
    # 開發模式
    if args.mode == 'dev':
        logger.info(f"🚀 啟動開發模式")
        logger.info(f"🌐 應用網址: http://{args.host}:{args.port}")
        logger.info(f"📚 API 文件: http://{args.host}:{args.port}/docs")
        logger.info(f"📖 ReDoc: http://{args.host}:{args.port}/redoc")
        logger.info(f"🔄 自動重載: 已啟用")
        logger.info("=" * 70)
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level=args.log_level
        )
    
    # 正式環境
    else:
        logger.info(f"🚀 啟動正式環境")
        logger.info(f"🌐 應用網址: http://{args.host}:{args.port}")
        logger.info(f"👷 Workers: {args.workers}")
        logger.info(f"📊 Log 層級: {args.log_level}")
        logger.info("=" * 70)
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level=args.log_level
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("\n\n👋 應用程式已停止")
        sys.exit(0)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.critical(f"❌ 嚴重錯誤: {e}", exc_info=True)
        sys.exit(1)