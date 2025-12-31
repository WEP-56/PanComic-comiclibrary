"""Application entry point."""
import sys
import os
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pancomic.core.logger import Logger
from pancomic.core.app import Application


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='PanComic - A unified multi-source comic reader'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to configuration file (default: user data directory)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='PanComic 0.3.0'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    # Parse command-line arguments
    args = parse_arguments()
    
    try:
        # Import global app setter
        from pancomic.core import app as app_module
        
        # Create and initialize application
        app = Application(config_path=args.config)
        
        # Set global instance
        app_module._app_instance = app
        
        if not app.initialize():
            Logger.error("Failed to initialize application")
            return 1
        
        # Run application
        exit_code = app.run()
        
        Logger.info(f"Application exiting with code {exit_code}")
        return exit_code
        
    except Exception as e:
        Logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
