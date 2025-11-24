export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  // for LiveKit Cloud Sandbox
  sandboxId?: string;
  agentName?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: "Café Coffee Day",
  pageTitle: "Café Coffee Day – Voice Barista",
  pageDescription: "Order your favourite Café Coffee Day beverage with a voice AI barista.",

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  // We'll add this logo file in the next sub-step
  logo: "/ccd-logo.svg",
  logoDark: "/ccd-logo.svg",

  // CCD-style colours
  accent: "#CC0000",      // CCD red
  accentDark: "#4A1E1E",  // dark coffee brown

  startButtonText: "Start wellness check-in",

  // not using LiveKit Cloud sandbox for now
  sandboxId: undefined,
  agentName: undefined,
};
