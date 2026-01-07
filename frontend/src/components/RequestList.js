import React from 'react';
import { Table } from 'antd';

const columns = [
  {
    title: '#',
    dataIndex: 'id',
    key: 'id',
  },
  {
    title: 'Method',
    dataIndex: 'method',
    key: 'method',
  },
  {
    title: 'Host',
    dataIndex: 'host',
    key: 'host',
  },
  {
    title: 'URL',
    dataIndex: 'url',
    key: 'url',
  },
];

const data = [
  {
    key: '1',
    id: 1,
    method: 'GET',
    host: 'example.com',
    url: '/index.html',
    request: {
      headers: 'GET /index.html HTTP/1.1\nHost: example.com\nUser-Agent: Mozilla/5.0',
      body: ''
    },
    response: {
      headers: 'HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: 1234',
      body: '<html><body><h1>Hello World</h1></body></html>'
    }
  },
  {
    key: '2',
    id: 2,
    method: 'POST',
    host: 'api.example.com',
    url: '/login',
    request: {
        headers: 'POST /login HTTP/1.1\nHost: api.example.com\nUser-Agent: Mozilla/5.0',
        body: '{"user":"admin","pass":"password"}'
      },
      response: {
        headers: 'HTTP/1.1 401 Unauthorized\nContent-Type: application/json',
        body: '{"error": "Invalid credentials"}'
      }
  },
];

const RequestList = ({ onSelectRequest }) => {
  return (
    <Table
      columns={columns}
      dataSource={data}
      onRow={(record) => ({
        onClick: () => {
          onSelectRequest(record);
        },
      })}
      rowClassName="clickable-row"
      pagination={false}
      scroll={{ y: 'calc(100vh - 200px)' }}
    />
  );
};

export default RequestList;
