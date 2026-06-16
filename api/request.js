import config from '../config';

const { baseUrl } = config;

function request(url, method = 'GET', data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      timeout: 60000,
      header: {
        'content-type': 'application/json',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }

        reject(
          new Error(
            (res.data && res.data.detail && res.data.detail.message) ||
              (res.data && res.data.message) ||
              `请求失败：${res.statusCode}`,
          ),
        );
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络请求失败'));
      },
    });
  });
}

export default request;
