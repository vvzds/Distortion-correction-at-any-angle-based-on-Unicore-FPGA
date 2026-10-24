# G4 static correction physical build — board test pending

接收：管理方/执行者先核对；一号协作者接收匹配采集显示整机；二号协作者执行并留档。

保持CMOS2、1920×1080@30、像素74.25MHz和DDR/校正125MHz。原G4 RTL/IP/FDC未修改，只调整原生PDS物理实现设置。PDS 2022.2-SP6.1报告All Constraints Met，DDR125慢角建立WNS=+0.183ns。报告通过仅指已约束检查，原始端口约束覆盖警告保留。

完整ZIP含匹配源码项目、IP、约束、实际检查点、构建日志、报告、真实参数、下载说明及sbit。ZIP和位流SHA256分别见qualified_package_receipt.json、VERSION.json。解压后运行08_文件校验.py检查完整性。完整源码PDS入口是01_project/full_source_1080p30.pds；检查点入口与源码入口明确区分。

没有烧录、没有发送UART、没有板测图像或实测校正新帧率，不能当作整机实板验收通过。此提交仅增加独立交付目录，没有替换仓库根目录的生产源码或位流。
