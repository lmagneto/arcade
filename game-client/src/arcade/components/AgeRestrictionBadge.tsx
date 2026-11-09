import { memo } from 'react';

function AgeRestrictionBadgeBase() {
  return (
    <div className="age" role="img" aria-label="18 plus only">
      <span className="age__big">18+</span>
      <span className="age__small">ONLY</span>
    </div>
  );
}

export const AgeRestrictionBadge = memo(AgeRestrictionBadgeBase);
