import React, { useState } from 'react';
import { Layout, Row, Col } from 'antd';
import MainHeader from './components/MainHeader';
import RequestList from './components/RequestList';
import RequestResponseViewer from './components/RequestResponseViewer';

const { Header, Content } = Layout;

function App() {
  const [selectedRequest, setSelectedRequest] = useState(null);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <MainHeader />
      </Header>
      <Content style={{ padding: '20px' }}>
        <Row gutter={16}>
          <Col span={8}>
            <RequestList onSelectRequest={setSelectedRequest} />
          </Col>
          <Col span={16}>
            <RequestResponseViewer request={selectedRequest} />
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}

export default App;