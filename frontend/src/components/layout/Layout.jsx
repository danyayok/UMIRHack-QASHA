import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({
  children,
  sidebarProps = {},
  headerProps = {},
  showSidebar = true,
  showHeader = true
}) => {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {showSidebar && <Sidebar {...sidebarProps} />}

      <div className="flex-1 flex flex-col">
        {showHeader && <Header {...headerProps} />}

        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

export const DashboardLayout = ({ children, ...props }) => (
  <Layout showSidebar showHeader {...props}>
    {children}
  </Layout>
);

export const AuthLayout = ({ children }) => (
  <Layout showSidebar={false} showHeader={false}>
    {children}
  </Layout>
);

export const ProjectLayout = ({ children, ...props }) => (
  <Layout showSidebar showHeader {...props}>
    {children}
  </Layout>
);

export default Layout;