
import { useEffect, useState } from 'react';

export function useStageScale(width: number, height: number): number {
  const getScale = () =>
    Math.max(
      window.innerWidth / width,
      window.innerHeight / height,
    );

  const [scale, setScale] = useState(getScale);

  useEffect(() => {
    const update = () => {
      setScale(getScale());
    };

    update();

    window.addEventListener('resize', update);

    return () => {
      window.removeEventListener('resize', update);
    };
  }, [width, height]);

  return scale;
}
