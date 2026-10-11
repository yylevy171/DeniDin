// Type-check shim: the app imports "react-native", which Vite aliases to react-native-web
// (vite.config.ts). @types/react-native-web would pull in all of react-native plus a second
// React 19 copy (~180 packages), so the few symbols we use are declared here instead. Our own
// components/props are fully type-checked; react-native-web component props are not.
declare module "react-native" {
  import type { ComponentType } from "react";

  export const View: ComponentType<any>;
  export const Text: ComponentType<any>;
  export const TextInput: ComponentType<any>;
  export const Pressable: ComponentType<any>;
  export const ScrollView: ComponentType<any>;
  export const Image: ComponentType<any>;
  export const AppRegistry: {
    registerComponent(appKey: string, getComponent: () => ComponentType<any>): string;
    runApplication(appKey: string, params: { rootTag: Element | null; initialProps?: object }): void;
  };
  export const I18nManager: {
    isRTL: boolean;
    allowRTL(allow: boolean): void;
    forceRTL(force: boolean): void;
  };
  export function useWindowDimensions(): { width: number; height: number; scale: number; fontScale: number };
}
