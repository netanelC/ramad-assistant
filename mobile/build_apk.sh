#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📱 Building Ramad Assistant Android APK..."

if ! command -v flutter &> /dev/null; then
    if [ -d "$HOME/flutter/bin" ]; then
        export PATH="$HOME/flutter/bin:$PATH"
    else
        echo "⚠️ Flutter SDK not found in PATH or ~/flutter/bin."
        echo "💡 To install Flutter: git clone https://github.com/flutter/flutter.git -b stable --depth 1 ~/flutter"
        echo "   Then run: export PATH=\"\$HOME/flutter/bin:\$PATH\""
        exit 1
    fi
fi

echo "📦 Resolving Flutter dependencies..."
flutter pub get

echo "⚙️ Compiling release APK..."
flutter build apk --release

echo "✅ APK build finished successfully!"
echo "📂 Output location: $SCRIPT_DIR/build/app/outputs/flutter-apk/app-release.apk"
