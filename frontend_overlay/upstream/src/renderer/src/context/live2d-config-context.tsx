import {
  createContext, useContext, useState, useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useConfig } from '@/context/character-config-context';

/**
 * Model emotion mapping interface
 * @interface EmotionMap
 */
interface EmotionMap {
  [key: string]: number | string;
}

/**
 * Motion weight mapping interface
 * @interface MotionWeightMap
 */
export interface MotionWeightMap {
  [key: string]: number;
}

/**
 * Tap motion mapping interface
 * @interface TapMotionMap
 */
export interface TapMotionMap {
  [key: string]: MotionWeightMap;
}

/**
 * Skin rendering mode
 * - 'live2d':       Use Cubism .moc3 model via PIXI live2d (full lipsync + motion)
 * - 'static_multi': One static PNG per emotion index (no lipsync but expressions switchable)
 * - 'static_single':One static PNG, no expression switching at all (lowest cost)
 *
 * When omitted, defaults to 'live2d' for backward compatibility.
 */
export type SkinType = 'live2d' | 'static_multi' | 'static_single';

/**
 * Live2D model information interface
 * @interface ModelInfo
 */
export interface ModelInfo {
  /** Model name */
  name?: string;

  /** Model description */
  description?: string;

  /** Model URL */
  url: string;

  /** Scale factor */
  kScale: number;

  /** Initial X position shift */
  initialXshift: number;

  /** Initial Y position shift */
  initialYshift: number;

  /** Idle motion group name */
  idleMotionGroupName?: string;

  /** Default emotion */
  defaultEmotion?: number | string;

  /** Emotion mapping configuration */
  emotionMap: EmotionMap;

  /** Enable pointer interactivity */
  pointerInteractive?: boolean;

  /** Tap motion mapping configuration */
  tapMotions?: TapMotionMap;

  /** Enable scroll to resize */
  scrollToResize?: boolean;

  /** Initial scale */
  initialScale?: number;

  // ===== Skin system (all optional, default = 'live2d') =====

  /** Rendering mode for this character. Omit = 'live2d' */
  skinType?: SkinType;

  /** Single static image URL. Used in 'static_single' and as fallback in 'static_multi' */
  staticUrl?: string;

  /**
   * Static images per emotion index, e.g. { "0": "/path/neutral.png", "1": "/path/joy.png" }.
   * Key is the integer emotion index from emotionMap, stored as string for JSON compatibility.
   * Used only in 'static_multi' mode.
   */
  sprites?: Record<string, string>;
}

/**
 * Live2D configuration context state interface
 * @interface Live2DConfigState
 */
interface Live2DConfigState {
  modelInfo?: ModelInfo;
  setModelInfo: (info: ModelInfo | undefined) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  /** Current expression index for static_multi skin (ignored by Live2D mode) */
  staticExpression: number;
  /** Setter used by use-audio-task to switch sprite when LLM emits an emo tag */
  setStaticExpression: (index: number) => void;
}

/**
 * Default values and constants
 */
const DEFAULT_CONFIG = {
  modelInfo: {
    scrollToResize: true,
  } as ModelInfo | undefined,
  isLoading: false,
};

/**
 * Create the Live2D configuration context
 */
export const Live2DConfigContext = createContext<Live2DConfigState | null>(null);

/**
 * Live2D Configuration Provider Component
 * @param {Object} props - Provider props
 * @param {React.ReactNode} props.children - Child components
 */
export function Live2DConfigProvider({ children }: { children: React.ReactNode }) {
  const { confUid } = useConfig();

  const [isLoading, setIsLoading] = useState(DEFAULT_CONFIG.isLoading);
  const [staticExpression, setStaticExpression] = useState<number>(0);

  const [modelInfo, setModelInfoState] = useLocalStorage<ModelInfo | undefined>(
    "modelInfo",
    DEFAULT_CONFIG.modelInfo,
    {
      filter: (value) => (value ? { ...value, url: "" } : value),
    },
  );

  // const [modelInfo, setModelInfoState] = useState<ModelInfo | undefined>(DEFAULT_CONFIG.modelInfo);

  const setModelInfo = (info: ModelInfo | undefined) => {
    if (!info) {
      setModelInfoState(undefined);
      return;
    }

    // Skin system: default to 'live2d' for backward compatibility.
    const skinType = info.skinType ?? 'live2d';

    // Validate per skin type:
    //   - 'live2d':       requires .url to .model3.json
    //   - 'static_single':requires staticUrl
    //   - 'static_multi': requires either staticUrl (fallback) or at least 1 sprites entry
    const validLive2d = skinType === 'live2d' && Boolean(info.url);
    const validStaticSingle = skinType === 'static_single' && Boolean(info.staticUrl);
    const validStaticMulti = skinType === 'static_multi'
      && (Boolean(info.staticUrl) || (info.sprites && Object.keys(info.sprites).length > 0));

    if (!validLive2d && !validStaticSingle && !validStaticMulti) {
      console.warn(`[Live2DConfig] Invalid model info for skinType=${skinType}, clearing.`, info);
      setModelInfoState(undefined);
      return;
    }

    // kScale * 2 is a Live2D-specific quirk; harmless for static modes (StaticAvatar ignores kScale).
    const finalScale = Number(info.kScale || 0.5) * 2;
    console.log(`Setting model info: skinType=${skinType}, scale=${finalScale}`);

    setModelInfoState({
      ...info,
      skinType,
      staticUrl: info.staticUrl ?? '',
      sprites: info.sprites ?? {},
      kScale: finalScale,
      pointerInteractive:
        "pointerInteractive" in info
          ? info.pointerInteractive
          : (modelInfo?.pointerInteractive ?? true),
      scrollToResize:
        "scrollToResize" in info
          ? info.scrollToResize
          : (modelInfo?.scrollToResize ?? true),
    });
  };

  const contextValue = useMemo(
    () => ({
      modelInfo,
      setModelInfo,
      isLoading,
      setIsLoading,
      staticExpression,
      setStaticExpression,
    }),
    [modelInfo, isLoading, setIsLoading, staticExpression],
  );

  return (
    <Live2DConfigContext.Provider value={contextValue}>
      {children}
    </Live2DConfigContext.Provider>
  );
}

/**
 * Custom hook to use the Live2D configuration context
 * @throws {Error} If used outside of Live2DConfigProvider
 */
export function useLive2DConfig() {
  const context = useContext(Live2DConfigContext);

  if (!context) {
    throw new Error('useLive2DConfig must be used within a Live2DConfigProvider');
  }

  return context;
}

// Export the provider as default
export default Live2DConfigProvider;
