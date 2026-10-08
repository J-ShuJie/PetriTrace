# PetriTrace

[English](README.md) · [Deutsch](README.de.md) · [中文](README.zh-CN.md)

PetriTrace是一套基于树莓派的培养皿观察工具，支持定时拍照、温湿度记录和菌落计数。项目包含控制软件、外壳设计与加工图纸，以及从材料准备到日常使用的完整手册。

![PetriTrace整机实物，正面配有触摸屏](docs/assets/manual/photos/front.jpg)

通过装置触摸屏或电脑、手机和平板的浏览器，可以控制拍摄、查看照片与历史记录，并导出数据用于后续分析。

## 获取项目

| 软件下载 | 制作图纸 | 完整手册 |
|---|---|---|
| [前往Releases](https://github.com/J-ShuJie/PetriTrace/releases) | [下载图纸](https://github.com/J-ShuJie/PetriTrace/releases) · [文件说明](#制作图纸) | [在线阅读](docs/PetriTrace制作与使用手册.md) · [下载PDF](docs/pdf/PetriTrace_Manual_zh.pdf) |
| Windows Setup安装包，包含部署管理器和树莓派端部署文件 | 19块板件的DWG加工图与OpenSCAD设计源文件 | 材料、装配、接线、部署和软件操作 |

软件、图纸和手册可以分别获取。已有树莓派和拍摄硬件时，可下载Setup安装包部署软件；外壳也可以采用自己的设计。软件源码在[项目仓库](https://github.com/J-ShuJie/PetriTrace)中提供。

## 软件功能

- **拍摄与照明**：单次拍照或按间隔自动拍摄，设置灯带亮度及拍照前后的照明时间。
- **环境与菌落记录**：查看两组传感器的温湿度记录，以及菌落计数随时间的变化。
- **照片与数据对照**：查看每次拍摄的照片、菌落计数和温湿度，并在历史图表中找到对应记录。
- **导出与整理**：按时间范围或所选记录导出照片和数据，也可以批量删除记录。
- **部署与维护**：通过部署管理器连接树莓派、安装软件、检查连接和执行修复。

![浏览器控制台：拍摄控制与环境、菌落历史图表](docs/assets/manual/ui/15_capture_overview_updated.png)

部署管理器提供Windows版本。部署完成后，树莓派独立运行拍摄与记录任务；日常使用可直接打开浏览器控制台。跨网络访问使用用户自己的Tailscale账户，树莓派和访问设备加入同一授权网络。

## 制作图纸

参考装置使用Raspberry Pi 5、Camera Module 3、5英寸Touch Display 2、Pico WH及扩展板，配合两路温湿度传感器和灯带。外壳由19块3 mm厚板件组成，包含五层屏幕框、活动门与磁吸组件。

![外壳板件分解图](docs/assets/manual/exploded.png)

| 文件 | 用途 |
|---|---|
| `PetriTrace_19parts_mm_DWG2007.dwg` | 已排版的板件加工图，单位为毫米，按1:1加工 |
| `PetriTrace_OpenSCAD.zip` | 可编辑的OpenSCAD模型源文件，包含所需依赖，支持分别打开19块板件 |

两份图纸保存在仓库的`hardware/`目录，也作为独立文件提供，下载入口见[Releases](https://github.com/J-ShuJie/PetriTrace/releases)。部件型号、螺丝与螺母用量、接线方式和装配步骤见完整手册。

## 开始制作与使用

1. **准备材料**：按手册选购电子件、紧固件，并加工3 mm厚板件。
2. **准备树莓派**：写入64位 Raspberry Pi OS Desktop，设置账户、网络和SSH。安装主板前插好microSD卡。
3. **装配与接线**：先在板件上固定电子件，再逐步拼合外壳并接线；Pico WH的准备方法见手册。
4. **部署软件**：在Windows电脑上运行Setup安装包，打开PetriTrace部署管理器，按向导连接树莓派并完成部署。部署时，电脑应能连接树莓派，树莓派需联网下载运行依赖。
5. **试拍与记录**：打开控制台，将培养皿放在上层框板的承托位置，试拍并检查照片、传感器数据和导出，再开始定时记录。

初次硬件装配预计约1.5小时，系统准备和软件部署另计。完整步骤与各项功能的操作方法见[《PetriTrace制作与使用手册》](docs/PetriTrace制作与使用手册.md)。

从源码构建软件的步骤见[英文构建指南](docs/BUILD.md)。

## 开源与反馈

项目作者：[J-ShuJie](https://github.com/J-ShuJie)。

项目自有软件、图纸和手册采用[MIT许可](LICENSE)，可以按自己的需要使用和修改。第三方组件的许可与署名见[第三方明细](THIRD_PARTY_NOTICES.md)。

遇到问题或希望提出建议，可以在[Issues](https://github.com/J-ShuJie/PetriTrace/issues)中描述；欢迎通过[Pull Request](https://github.com/J-ShuJie/PetriTrace/pulls)贡献改进。
