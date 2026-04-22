/**
 * StaticAvatar - Renders the desktop pet using static PNG sprites instead of Live2D.
 *
 * Used when ModelInfo.skinType is 'static_single' or 'static_multi'.
 *
 * Why this exists:
 *   The Live2D component (live2d.tsx) is the sole place that calls useAudioTask /
 *   useInterrupt / useIpcHandlers. If we conditionally skip Live2D, those hooks
 *   never run and audio playback stops. So StaticAvatar must call the same set of
 *   hooks to keep the conversation pipeline alive.
 *
 * Design choices:
 *   - No PIXI / no Live2D SDK. Just an <img> with a CSS breathe animation.
 *   - Sprite source comes from ModelInfo.sprites[index] (multi) or staticUrl (single).
 *   - When the requested expression index is missing in sprites, falls back to
 *     sprites['0'] then to staticUrl.
 *   - Pet-mode right-click menu is wired the same way as Live2D (window.api.showContextMenu).
 */

import { memo, useMemo, useRef } from "react";
import { Box } from "@chakra-ui/react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useIpcHandlers } from "@/hooks/utils/use-ipc-handlers";
import { useInterrupt } from "@/hooks/utils/use-interrupt";
import { useAudioTask } from "@/hooks/utils/use-audio-task";
import { useForceIgnoreMouse } from "@/hooks/utils/use-force-ignore-mouse";
import { useMode } from "@/context/mode-context";

export const StaticAvatar = memo((): JSX.Element => {
  const { modelInfo, staticExpression } = useLive2DConfig();
  const { mode } = useMode();
  const { forceIgnoreMouse } = useForceIgnoreMouse();
  const containerRef = useRef<HTMLDivElement>(null);
  const isPet = mode === "pet";

  // Keep audio / interrupt / IPC pipelines alive even when Live2D is not mounted.
  useIpcHandlers();
  useInterrupt();
  useAudioTask();

  // Decide which image to show this render.
  const currentSrc = useMemo(() => {
    if (!modelInfo) return "";

    if (modelInfo.skinType === "static_multi" && modelInfo.sprites) {
      const key = String(staticExpression);
      return (
        modelInfo.sprites[key]
        ?? modelInfo.sprites["0"]
        ?? modelInfo.staticUrl
        ?? ""
      );
    }

    // static_single (and any unknown skin type that still has staticUrl)
    return modelInfo.staticUrl ?? "";
  }, [modelInfo, staticExpression]);

  const handleContextMenu = (e: React.MouseEvent) => {
    if (!isPet) return;
    e.preventDefault();
    console.log("[ContextMenu] (Pet Mode, Static) Right-click detected, requesting menu...");
    window.api?.showContextMenu?.();
  };

  return (
    <div
      ref={containerRef}
      id="static-avatar-wrapper"
      style={{
        width: "100%",
        height: "100%",
        pointerEvents: isPet && forceIgnoreMouse ? "none" : "auto",
        overflow: "hidden",
        position: "relative",
      }}
      onContextMenu={handleContextMenu}
    >
      <Box
        position="absolute"
        bottom={0}
        left={0}
        width="100%"
        height="100%"
        display="flex"
        alignItems="flex-end"
        justifyContent="center"
        paddingBottom="20vh"
        pointerEvents="none"
      >
        {currentSrc ? (
          <img
            src={currentSrc}
            alt="character avatar"
            draggable={false}
            style={{
              maxHeight: "100%",
              maxWidth: "100%",
              objectFit: "contain",
              userSelect: "none",
              animation: "avatarBreathe 4s ease-in-out infinite",
              // crispier rendering on integer-scale displays
              imageRendering: "auto",
            }}
          />
        ) : (
          <Box color="gray.400" fontSize="sm">
            (No avatar image configured. Set staticUrl or sprites in model_dict.json.)
          </Box>
        )}
      </Box>

      {/* keyframe defined inline so the component is self-contained */}
      <style>{`
        @keyframes avatarBreathe {
          0%, 100% { transform: translateY(0) scale(1); }
          50%      { transform: translateY(-6px) scale(1.005); }
        }
      `}</style>
    </div>
  );
});

StaticAvatar.displayName = "StaticAvatar";

export default StaticAvatar;
