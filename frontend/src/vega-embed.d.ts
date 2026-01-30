declare module 'vega-embed' {
  import { Spec } from 'vega-lite';
  
  interface EmbedOptions {
    actions?: boolean;
    renderer?: 'canvas' | 'svg';
    width?: number;
    height?: number;
    theme?: string;
    config?: Record<string, unknown>;
  }
  
  interface Result {
    view: unknown;
    spec: unknown;
    vgSpec: unknown;
    finalize: () => void;
  }
  
  function embed(
    el: HTMLElement | string,
    spec: Spec | Record<string, unknown>,
    options?: EmbedOptions
  ): Promise<Result>;
  
  export default embed;
}
