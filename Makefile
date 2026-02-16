# Makefile for YT-DLD DEB package

PACKAGE_NAME = yt-dld
VERSION = 1.0.0
ARCH = amd64
DEB_FILE = $(PACKAGE_NAME)_$(VERSION)_$(ARCH).deb
BUILD_DIR = debian/$(PACKAGE_NAME)
YT_DLP_URL = https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux.zip
TEMP_ZIP = yt-dlp_linux.zip
TEMP_DIR = yt-dlp_temp

.PHONY: all clean build install test update-yt-dlp

all: build

# Download and extract latest yt-dlp
update-yt-dlp:
	@echo "Downloading latest yt-dlp from GitHub..."
	@curl -L -o $(TEMP_ZIP) $(YT_DLP_URL)
	@echo "Extracting yt-dlp..."
	@rm -rf $(TEMP_DIR)
	@unzip -o $(TEMP_ZIP) -d $(TEMP_DIR)
	@mv $(TEMP_DIR)/yt-dlp_linux yt-dlp
	@chmod +x yt-dlp
	@cp -r $(TEMP_DIR)/_internal .
	@rm -rf $(TEMP_DIR) $(TEMP_ZIP)
	@echo "yt-dlp updated to latest version!"

build:
	@echo "Building $(DEB_FILE)..."
	@mkdir -p $(BUILD_DIR)/usr/bin
	@mkdir -p $(BUILD_DIR)/usr/share/$(PACKAGE_NAME)
	@mkdir -p $(BUILD_DIR)/usr/share/applications
	@mkdir -p $(BUILD_DIR)/usr/share/pixmaps
	@mkdir -p $(BUILD_DIR)/DEBIAN
	
	@echo "Copying executables..."
	@cp yt-dlp $(BUILD_DIR)/usr/bin/
	@cp yt_dlp_gui $(BUILD_DIR)/usr/share/$(PACKAGE_NAME)/
	@cp yt-dlp $(BUILD_DIR)/usr/share/$(PACKAGE_NAME)/
	
	@echo "Copying internal files..."
	@cp -r _internal $(BUILD_DIR)/usr/share/$(PACKAGE_NAME)/
	@cp -r ffmpeg_tools $(BUILD_DIR)/usr/share/$(PACKAGE_NAME)/
	
	@echo "Copying desktop files..."
	@cp debian/yt-dld-gui $(BUILD_DIR)/usr/bin/
	@cp debian/yt-dld.desktop $(BUILD_DIR)/usr/share/applications/
	@cp app_icon.png $(BUILD_DIR)/usr/share/pixmaps/$(PACKAGE_NAME).png
	
	@echo "Setting permissions..."
	@chmod +x $(BUILD_DIR)/usr/bin/yt-dld-gui
	
	@echo "Creating DEBIAN/control..."
	@echo "Package: $(PACKAGE_NAME)" > $(BUILD_DIR)/DEBIAN/control
	@echo "Version: $(VERSION)" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Architecture: $(ARCH)" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Maintainer: YT-DLD Developer <developer@example.com>" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Description: GUI for yt-dlp - YouTube video downloader" >> $(BUILD_DIR)/DEBIAN/control
	@echo " A powerful graphical user interface for yt-dlp, allowing you to download" >> $(BUILD_DIR)/DEBIAN/control
	@echo " videos from YouTube and many other video platforms." >> $(BUILD_DIR)/DEBIAN/control
	@echo " ." >> $(BUILD_DIR)/DEBIAN/control
	@echo " Features include:" >> $(BUILD_DIR)/DEBIAN/control
	@echo "  - Easy-to-use graphical interface" >> $(BUILD_DIR)/DEBIAN/control
	@echo "  - Support for multiple video formats" >> $(BUILD_DIR)/DEBIAN/control
	@echo "  - Batch downloading" >> $(BUILD_DIR)/DEBIAN/control
	@echo "  - Download queue management" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Section: video" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Priority: optional" >> $(BUILD_DIR)/DEBIAN/control
	@echo "Depends: ffmpeg" >> $(BUILD_DIR)/DEBIAN/control
	
	@echo "Building DEB package..."
	@dpkg-deb --build --root-owner-group $(BUILD_DIR) $(DEB_FILE)
	@echo "Package created: $(DEB_FILE)"

install: build
	@echo "Installing $(DEB_FILE)..."
	@sudo dpkg -i $(DEB_FILE)

test: build
	@echo "Testing package contents..."
	@dpkg-deb -c $(DEB_FILE) | head -20

clean:
	@echo "Cleaning build directory..."
	@rm -rf $(BUILD_DIR)
	@rm -f $(DEB_FILE)

rebuild: clean update-yt-dlp build

help:
	@echo "YT-DLD Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  build           - Build the DEB package (requires running update-yt-dlp first)"
	@echo "  update-yt-dlp  - Download latest yt-dlp version"
	@echo "  install         - Build and install the package"
	@echo "  test            - Show package contents"
	@echo "  clean           - Remove build artifacts"
	@echo "  rebuild         - Clean, update yt-dlp and rebuild the package"
	@echo "  help            - Show this help message"
