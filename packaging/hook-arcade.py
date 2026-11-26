from PyInstaller.utils.hooks import collect_data_files, get_package_paths

hiddenimports = ["arcade.gl.backends.opengl.provider", "arcade.gl.backends.opengl"]

# Keep arcade/VERSION as a file. Arcade 3.3.3's stock hook uses it as a directory.
datas = collect_data_files("arcade")
_, pymunk_path = get_package_paths("pymunk")
binaries = [(pymunk_path + "/_chipmunk.pyd", ".")]
