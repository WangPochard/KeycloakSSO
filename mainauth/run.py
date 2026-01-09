"""
FastAPI 應用程式啟動腳本
支援多種啟動模式和資料庫管理
"""
import uvicorn
import sys
import os
import argparse
import logging
from datetime import datetime

# 確保可以 import app
sys.path.insert(0, os.path.dirname(__file__))

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
    """檢查資料庫連接"""
    try:
        from app.database import engine
        
        with engine.connect() as conn:
            print("資料庫連接成功")
            return True
    except Exception as e:
        print(f"資料庫連接失敗: {e}")
        return False


def init_database():
    """初始化資料庫（建立表）"""
    print("正在初始化資料庫...")
    try:
        from app.database import engine, Base
        from app.models import User, SubSystem, AuthorizationCode
        
        Base.metadata.create_all(bind=engine)
        
        print("資料庫初始化完成")
        
        return True
    except Exception as e:
        print(f"資料庫初始化失敗: {e}")
        return False


def drop_database():
    """刪除所有資料表"""
    print("警告：即將刪除所有資料表（包含所有資料）！")
    
    try:
        from app.database import engine, Base
        
        print("正在刪除資料表...")
        Base.metadata.drop_all(bind=engine, checkfirst=False)
        print("所有資料表已刪除")
        
        return True
    except Exception as e:
        print(f"刪除失敗: {e}")
        return False


def truncate_database():
    """清空資料表內容（保留結構）"""
    print("警告：即將清空所有資料表的內容（保留表結構）！")
    
    try:
        from app.database import engine
        from sqlalchemy import text
        
        print("正在清空資料表...")
        
        with engine.connect() as conn:
            # 先刪除有外鍵的表
            conn.execute(text("TRUNCATE TABLE authorization_codes CASCADE;"))
            conn.commit()
            
            # 再刪除主表
            conn.execute(text("TRUNCATE TABLE subsystems CASCADE;"))
            conn.commit()
            
            conn.execute(text("TRUNCATE TABLE users CASCADE;"))
            conn.commit()
        
        print("資料表已清空（結構保留）")
        
        return True
    except Exception as e:
        print(f"清空失敗: {e}")
        return False


def reset_database():
    """重置資料庫（刪除後重建）"""
    print("警告：即將重置資料庫（所有資料將遺失）！")
    
    print("步驟 1/2: 刪除現有資料表...")
    try:
        from app.database import engine, Base
        Base.metadata.drop_all(bind=engine)
        print("資料表已刪除")
    except Exception as e:
        print(f"刪除失敗: {e}")
        return False
    
    print("步驟 2/2: 重新建立資料表...")
    return init_database()


def main():
    """主函數"""
    args = parse_args()
    
    print("=" * 70)
    print("FastAPI SSO 主系統啟動中...")
    print("=" * 70)
    
    if not check_database_connection():
        sys.exit(1)
    
    if args.drop_db:
        if drop_database():
            print("操作完成")
        else:
            print("操作失敗")
        sys.exit(0)
    
    if args.truncate_db:
        if truncate_database():
            print("操作完成")
        else:
            print("操作失敗")
        sys.exit(0)
    
    if args.reset_db:
        if reset_database():
            print("資料庫已重置")
        else:
            print("重置失敗")
            sys.exit(1)
    
    if args.init_db:
        if not init_database():
            sys.exit(1)
    
    print("=" * 70)
    
    if args.mode == 'dev':
        print(f"啟動開發模式")
        print(f"應用網址: http://{args.host}:{args.port}")
        print(f"API 文件: http://{args.host}:{args.port}/docs")
        print("=" * 70)
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level=args.log_level
        )
    
    else:
        print(f"啟動正式環境")
        print(f"應用網址: http://{args.host}:{args.port}")
        print(f"Workers: {args.workers}")
        print("=" * 70)
        
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
        print("\n應用程式已停止")
        sys.exit(0)
    except Exception as e:
        print(f"嚴重錯誤: {e}")
        sys.exit(1)