// OHIF v3 runtime config. Mounted over the image's default app-config.js.
// Data source is same-origin (/dicom-web) so there is no CORS to configure —
// the internal nginx router serves OHIF and Orthanc under one host.
window.config = {
  routerBasename: '/',
  showStudyList: true,
  extensions: [],
  modes: [],
  defaultDataSourceName: 'dicomweb',
  dataSources: [
    {
      friendlyName: 'Imaging Sandbox (Orthanc)',
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',
      configuration: {
        name: 'orthanc',
        wadoUriRoot: '/dicom-web',
        qidoRoot: '/dicom-web',
        wadoRoot: '/dicom-web',
        qidoSupportsIncludeField: true,
        supportsReject: false,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: false,
        supportsWildcard: true,
        omitQuotationForMultipartRequest: true,
        // Read-only public instance: no STOW from the browser.
        dicomUploadEnabled: false,
      },
    },
  ],
};
