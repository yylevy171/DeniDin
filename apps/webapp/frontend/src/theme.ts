// White / green / black palette (DeniDin brand), light + dark.
export type ThemeName = "light" | "dark";

export interface Theme {
  name: ThemeName;
  bg: string;
  surface: string;
  surfaceAlt: string;
  border: string;
  text: string;
  textDim: string;
  accent: string;
  accentText: string;
  bubbleMine: string;
  bubbleTheirs: string;
  danger: string;
}

const green = "#1c7c54";
const greenSoft = "#e4f3ec";

export const THEMES: Record<ThemeName, Theme> = {
  light: {
    name: "light",
    bg: "#f4f6f5",
    surface: "#ffffff",
    surfaceAlt: "#f0f3f1",
    border: "#d8e0dc",
    text: "#12211b",
    textDim: "#5b6b64",
    accent: green,
    accentText: "#ffffff",
    bubbleMine: greenSoft,
    bubbleTheirs: "#ffffff",
    danger: "#b23b3b",
  },
  dark: {
    name: "dark",
    bg: "#0e1512",
    surface: "#16211c",
    surfaceAlt: "#1d2b24",
    border: "#2c3d34",
    text: "#eaf2ee",
    textDim: "#9db1a8",
    accent: "#3fae7c",
    accentText: "#08120d",
    bubbleMine: "#20402f",
    bubbleTheirs: "#1d2b24",
    danger: "#e77373",
  },
};
