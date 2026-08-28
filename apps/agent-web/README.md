# Agent Web Trial Mock

This is a local, non-release visual trial for the React Agent workbench. It has no API client,
no authentication, and no connection to project, thread, or Run data.

The visual language is a small, independent implementation based on the layout and theme
patterns in `research/deepseek-harness`: a light-first conversation workspace, a blue-gray
sidebar, optional details, capsule controls, and matching dark-mode tokens. It does not copy
DeepSeek branding, its plugin shell, runtime protocol, or client packages.

## Start

```bash
npm install
npm run dev
```

Open `http://localhost:4173`.

The trial intentionally covers the product shell only: project/thread navigation, a durable-run
style timeline, an in-stream approval card, optional inspector, theme switching, and responsive
rail/drawer states. Production integration remains governed by
`openspec/changes/add-react-agent-web/`.

When this trial moves beyond mock data, retain the visual shell but connect it through the
governed `agent-web -> platform-api -> runtime-service` path. Existing Platform Web screens
should be introduced as explicit entry points or rebuilt React views around their contracts;
Vue components and DeepSeek Harness packages are not drop-in dependencies.
