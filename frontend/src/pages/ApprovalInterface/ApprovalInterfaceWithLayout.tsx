/**
 * ApprovalInterfaceWithLayout.tsx
 *
 * Example integration of ApprovalInterface with DesktopLayout
 * Shows how to wrap existing pages with the new layout system
 */

import React from 'react';
import { DesktopLayout } from '../../layouts/DesktopLayout';
import { ApprovalInterface } from './ApprovalInterface';

export const ApprovalInterfaceWithLayout: React.FC = () => {
  return (
    <DesktopLayout
      showRail={true}
      showSidebar={true}
      showRightSidebar={true}
    >
      <ApprovalInterface />
    </DesktopLayout>
  );
};

export default ApprovalInterfaceWithLayout;
