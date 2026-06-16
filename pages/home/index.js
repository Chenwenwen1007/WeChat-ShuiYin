import request from '../../api/request';
import config from '../../config';

function detectInputMode(text) {
  const value = (text || '').trim();
  if (!value) {
    return 'parse';
  }

  const directLinkKeywords = [
    'douyinvod.com/',
    'mime_type=video_mp4',
    'real_host=',
    '.mp4',
    '/video/tos/',
    '.0kkkkkt.com',
    '.cjjd14.com',
  ];

  if (directLinkKeywords.some((item) => value.includes(item))) {
    return 'direct';
  }

  return 'parse';
}

Page({
  data: {
    activeModule: 'parser',
    activeVariant: 'no_watermark',
    importMode: 'auto',
    parseMode: 'auto',
    inputText: '',
    loading: false,
    errorMessage: '',
    parseResult: null,
    videoUrl: '',
    coverUrl: '',
    currentVideoSource: '',
    currentDownloadSource: '',
    variantNote: '',
    showDetail: false,
    apiBaseUrl: config.baseUrl,
    modules: [
      {
        key: 'parser',
        title: '短视频解析',
        desc: '支持抖音、快手、小红书分享链接解析、预览与保存。',
        status: '可用',
      },
      {
        key: 'copy',
        title: '文案暂存',
        desc: '后续可扩展常用创作文案、标题模板、口播结构。',
        status: '规划中',
      },
      {
        key: 'assets',
        title: '素材清单',
        desc: '后续可扩展你自己的素材来源、选题链接和收集记录。',
        status: '规划中',
      },
    ],
  },

  switchModule(event) {
    const { key } = event.currentTarget.dataset;
    this.setData({ activeModule: key });
  },

  switchImportMode(event) {
    const { mode } = event.currentTarget.dataset;
    this.setData({
      importMode: mode,
      errorMessage: '',
    });
  },

  switchParseMode(event) {
    const { mode } = event.currentTarget.dataset;
    this.setData({
      parseMode: mode,
      errorMessage: '',
    });
  },

  toggleDetail() {
    this.setData({
      showDetail: !this.data.showDetail,
    });
  },

  handleInput(event) {
    this.setData({
      inputText: event.detail.value,
      errorMessage: '',
    });
  },

  pasteClipboard() {
    wx.getClipboardData({
      success: ({ data }) => {
        this.setData({
          inputText: data || '',
          errorMessage: '',
          activeModule: 'parser',
        });
      },
      fail: () => {
        wx.showToast({
          title: '读取剪贴板失败',
          icon: 'none',
        });
      },
    });
  },

  applyVariant(result, variant) {
    const isNoWatermark = variant === 'no_watermark';
    const videoUrl = isNoWatermark
      ? result.no_watermark_preview_video_url || result.watermark_preview_video_url
      : result.watermark_preview_video_url || result.preview_video_url;
    const currentVideoSource = isNoWatermark
      ? result.no_watermark_video_url || result.watermark_video_url
      : result.watermark_video_url;
    const currentDownloadSource = isNoWatermark
      ? result.no_watermark_download_url || result.watermark_download_url
      : result.watermark_download_url;

    // 根据解析来源和无水印验证状态生成提示
    let variantNote;
    if (isNoWatermark) {
      variantNote = result.no_watermark_note || '当前为无水印链路。';
    } else {
      variantNote = '当前为平台原始播放链路，稳定但通常带平台水印。';
    }

    this.setData({
      activeVariant: variant,
      videoUrl,
      currentVideoSource,
      currentDownloadSource,
      coverUrl: result.preview_cover_url,
      variantNote,
      showDetail: false,
    });
  },

  switchVariant(event) {
    const { variant } = event.currentTarget.dataset;
    const { parseResult } = this.data;
    if (!parseResult || !parseResult.watermark_video_url) {
      return;
    }
    this.applyVariant(parseResult, variant);
  },

  async parseVideo() {
    const { inputText, parseMode } = this.data;
    const response = await request('/api/parse', 'POST', {
      text: inputText.trim(),
      mode: parseMode,
    });
    
    let result;
    try {
      if (response && response.data && response.data.data) {
        result = response.data.data;
      } else if (response && response.data) {
        result = response.data;
      } else {
        result = response;
      }
    } catch (e) {
      result = response;
    }

    this.setData({ parseResult: result });
    
    const shouldUseNoWatermark = result && result.no_watermark_video_url && result.no_watermark_video_url.length > 0;
    this.applyVariant(result, shouldUseNoWatermark ? 'no_watermark' : 'watermark');
  },

  async importDirectLink() {
    const { inputText } = this.data;
    const response = await request('/api/direct-link', 'POST', {
      text: inputText.trim(),
    });
    const result = response.data;

    this.setData({
      parseResult: result,
      videoUrl: result.preview_url,
      coverUrl: '',
      currentVideoSource: result.source_url,
      currentDownloadSource: result.download_url,
      variantNote: '当前为手动导入的外部直链，适合直接使用插件拿到的最终视频地址。',
    });
  },

  async submitInput() {
    const { inputText, importMode } = this.data;
    const trimmed = inputText.trim();

    if (!trimmed) {
      wx.showToast({
        title: '请先粘贴链接',
        icon: 'none',
      });
      return;
    }

    const actualMode = importMode === 'auto' ? detectInputMode(trimmed) : importMode;

    this.setData({
      loading: true,
      errorMessage: '',
      parseResult: null,
      videoUrl: '',
      coverUrl: '',
      currentVideoSource: '',
      currentDownloadSource: '',
      variantNote: actualMode === 'direct'
        ? '已自动识别为外部视频直链。'
        : '',
      activeModule: 'parser',
    });

    try {
      if (actualMode === 'direct') {
        await this.importDirectLink();
      } else {
        await this.parseVideo();
      }
    } catch (error) {
      this.setData({
        errorMessage: error.message || '处理失败，请稍后再试',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  saveVideo() {
    const { currentDownloadSource, currentVideoSource } = this.data;
    console.log('保存视频:', { currentDownloadSource, currentVideoSource });
    
    if (!currentDownloadSource) {
      wx.showToast({
        title: '当前没有可保存的视频',
        icon: 'none',
      });
      return;
    }

    wx.showLoading({
      title: '下载中',
      mask: true,
    });

    wx.downloadFile({
      url: currentDownloadSource,
      success: ({ statusCode, tempFilePath }) => {
        if (statusCode < 200 || statusCode >= 300) {
          wx.hideLoading();
          wx.showToast({
            title: `下载失败：${statusCode}`,
            icon: 'none',
          });
          return;
        }

        wx.saveVideoToPhotosAlbum({
          filePath: tempFilePath,
          success: () => {
            wx.hideLoading();
            wx.showToast({
              title: '已保存到相册',
              icon: 'success',
            });
          },
          fail: (error) => {
            wx.hideLoading();
            if (
              error.errMsg &&
              (error.errMsg.includes('auth deny') || error.errMsg.includes('authorize'))
            ) {
              wx.showModal({
                title: '需要相册权限',
                content: '请在设置中允许保存到相册后重试。',
                showCancel: false,
              });
              return;
            }

            wx.showToast({
              title: '保存失败，请稍后再试',
              icon: 'none',
            });
          },
        });
      },
      fail: (error) => {
        wx.hideLoading();
        wx.showToast({
          title: error.errMsg || '下载失败',
          icon: 'none',
        });
      },
    });
  },

  copyDownloadLink() {
    const { currentVideoSource } = this.data;
    if (!currentVideoSource) {
      return;
    }

    wx.setClipboardData({
      data: currentVideoSource,
      success: () => {
        wx.showToast({
          title: '已复制当前视频地址',
          icon: 'none',
        });
      },
    });
  },
});
