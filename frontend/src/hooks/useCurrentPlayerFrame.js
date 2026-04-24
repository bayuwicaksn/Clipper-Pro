import { useCallback, useSyncExternalStore } from 'react';

export const useCurrentPlayerFrame = (ref, isPlayerReady) => {
  const subscribe = useCallback(
    (onStoreChange) => {
      const { current } = ref;
      if (!current) {
        return () => undefined;
      }
      
      const updater = () => {
        onStoreChange();
      };
      
      current.addEventListener('frameupdate', updater);
      return () => {
        current.removeEventListener('frameupdate', updater);
      };
    },
    [ref, isPlayerReady]
  );

  const data = useSyncExternalStore(
    subscribe,
    () => ref.current?.getCurrentFrame() ?? 0,
    () => 0
  );

  return data;
};
