import React from 'react';
import { Switch, Typography } from 'antd';

const { Title } = Typography;

const MainHeader = () => {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Title level={3} style={{ color: 'white', margin: 0 }}>Burpsuite TekUp Edition</Title>
      <Switch
        checkedChildren="Interception On"
        unCheckedChildren="Interception Off"
      />
    </div>
  );
};

export default MainHeader;
