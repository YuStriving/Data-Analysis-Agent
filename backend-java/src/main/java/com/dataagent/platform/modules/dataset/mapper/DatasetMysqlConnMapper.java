package com.dataagent.platform.modules.dataset.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataagent.platform.modules.dataset.domain.po.DatasetMysqlConnPO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DatasetMysqlConnMapper extends BaseMapper<DatasetMysqlConnPO> {
}
