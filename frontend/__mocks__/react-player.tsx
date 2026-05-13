import React from "react";

const ReactPlayer = React.forwardRef((_props: Record<string, unknown>, ref: React.Ref<{ seekTo: (n: number) => void }>) => {
  React.useImperativeHandle(ref, () => ({ seekTo: jest.fn() }));
  return <div data-testid="react-player" />;
});
ReactPlayer.displayName = "ReactPlayer";

export default ReactPlayer;
