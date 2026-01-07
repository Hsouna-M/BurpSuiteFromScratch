import React from 'react';
import { Card, Tabs, Input, Button } from 'antd';

const { TabPane } = Tabs;
const { TextArea } = Input;

const RequestResponseViewer = ({ request }) => {
  if (!request) {
    return <Card title="Select a request to view details" style={{ height: '100%' }} />;
  }

  return (
    <Card title={`Details for Request #${request.id}`}>
      <Tabs defaultActiveKey="1">
        <TabPane tab="Request" key="1">
          <TextArea rows={10} value={request.request.headers} />
          <TextArea rows={10} value={request.request.body} style={{ marginTop: '10px' }} />
        </TabPane>
        <TabPane tab="Response" key="2">
          <TextArea rows={10} value={request.response.headers} />
          <TextArea rows={10} value={request.response.body} style={{ marginTop: '10px' }} />
        </TabPane>
      </Tabs>
      <div style={{ marginTop: '20px' }}>
        <Button type="primary">Forward</Button>
        <Button danger style={{ marginLeft: '10px' }}>Drop</Button>
        <Button style={{ marginLeft: '10px' }}>Save</Button>
        <Button style={{ marginLeft: '10px' }}>Manual Edit</Button>
        <Button style={{ marginLeft: '10px' }}>Bruteforce</Button>
      </div>
    </Card>
  );
};

export default RequestResponseViewer;
